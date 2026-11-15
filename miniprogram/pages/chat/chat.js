const { request, clearElderSession } = require('../../utils/request.js');
const config = require('../../utils/config.js');
const { normalizeReply } = require('../../utils/format.js');
const { PHRASE_GROUPS, QUICK_PHRASES, DEFAULT_SPEAK_SPEED, normalizeSpeakSpeed } = require('../../utils/constants.js');
const { getUserId } = require('../../utils/user.js');
const { shouldHidePhrase } = require('../../utils/taboo.js');
const REPLY_TIMEOUT_MS = 8000;
// 内存里只保留最近这么多条，避免长会话把 scroll-view 的节点数堆到几百个
const MAX_MESSAGES = 200;
// 切 tab 很频繁，画像与留言短时间内不重复拉
const NOTE_REFRESH_MS = 5000;
const GREETING_REFRESH_MS = 30000;

Page({
  data: {
    user_id: '',
    thread_id: '',
    greeting: '您好',
    messages: [],
    input: '',
    sending: false,
    recording: false,
    translating: false,
    voiceLabel: '点一下说话',
    autoSendVoice: true,
    autoSpeak: true,
    speakSpeed: DEFAULT_SPEAK_SPEED,
    pendingText: '',
    pendingCountdown: 0,
    familyNote: null,
    noteOpen: false,
    ended: false,
    scrollInto: '',
    showNotice: false,
    wallExpanded: false,
    dockHeight: 300,
    quickPhrases: QUICK_PHRASES,
    quickTexts: [
      { label: '再说一遍', text: '再说一遍' },
      { label: '慢一点', text: '慢一点' },
      { label: '不聊了', text: '不聊了' },
    ],
    phraseGroups: PHRASE_GROUPS,
  },

  onLoad() {
    let threadId = wx.getStorageSync('thread_id');
    if (!threadId) {
      threadId = this._genThreadId();
      wx.setStorageSync('thread_id', threadId);
    }
    const history = wx.getStorageSync('chat_history_' + threadId) || [];
    const restored = (Array.isArray(history) ? history : []).map((item, index) => ({
      role: item.role || 'assistant',
      content: item.content,
      ts: item.ts || 0,
      // 老版本存的记录没有 uid，补一个稳定值，保证列表按 uid 复用节点
      uid: item.uid || 'h' + index + '_' + (item.ts || 0),
    }));
    this.setData({
      user_id: getUserId(),
      thread_id: threadId,
      messages: restored,
      scrollInto: restored.length ? 'msg-' + (restored.length - 1) : '',
      showNotice: !wx.getStorageSync('notice_read'),
    });
    this.loadGreeting();
    this.loadFamilyNote();
    this._initRecorder();
    this._initAudio();
  },

  onReady() {
    this._measureDock();
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 0 });
    }
    this._syncThread();
    this._loadVoiceSettings();
    this.loadFamilyNote();
    this.maybeGreet();
    this._measureDock();
  },

  // 「我的」页可能把 thread_id 换掉（清空对话），而它不一定能拿到聊天页实例。
  // 这里以 storage 为准做一次对齐，两条入口都能生效。
  _syncThread() {
    const stored = wx.getStorageSync('thread_id');
    if (!stored || stored === this.data.thread_id) return;
    this._clearPendingTimers();
    this._cancelPersist();
    this._stopAudio();
    const history = wx.getStorageSync('chat_history_' + stored) || [];
    const restored = (Array.isArray(history) ? history : []).map((item, index) => ({
      role: item.role || 'assistant',
      content: item.content,
      ts: item.ts || 0,
      uid: item.uid || 'h' + index + '_' + (item.ts || 0),
    }));
    this.setData(
      {
        thread_id: stored,
        messages: restored,
        ended: false,
        input: '',
        pendingText: '',
        pendingCountdown: 0,
        scrollInto: restored.length ? 'msg-' + (restored.length - 1) : '',
      },
      () => this._measureDock()
    );
    this._greetingFetchedAt = 0;
    this.loadGreeting();
  },

  onTabReselect() {
    if (!this.data.messages.length) return;
    this.setData({ scrollInto: '' }, () => {
      this.setData({ scrollInto: 'msg-0' });
    });
  },

  onHide() {
    this._stopAudio();
    this._persist();
  },

  onUnload() {
    this._clearPendingTimers();
    this._stopAudio();
    this._persist();
    if (this._audio && this._audio.destroy) {
      this._audio.destroy();
      this._audio = null;
    }
  },

  _initRecorder() {
    this._recorder = wx.getRecorderManager();
    this._recorder.onStart(() => {
      this._voiceStarting = false;
      this.setData({ recording: true, voiceLabel: '正在听…再点一下结束' });
      this._voiceMaxTimer = setTimeout(() => {
        if (this.data.recording) this._recorder.stop();
      }, 60000);
    });
    this._recorder.onStop((res) => {
      this._voiceStarting = false;
      this._clearVoiceMaxTimer();
      this.setData({ recording: false, translating: true, voiceLabel: '正在听…' });
      const dur = res && res.duration ? res.duration : 0;
      if (dur < 1000) {
        this.setData({ translating: false, voiceLabel: '点一下说话' });
        wx.showToast({ title: '太短了，您多说两句', icon: 'none' });
        return;
      }
      const path = res && res.tempFilePath;
      if (!path) {
        this.setData({ translating: false, voiceLabel: '点一下说话' });
        wx.showToast({ title: '这会儿听不清，您打字也行', icon: 'none' });
        return;
      }
      wx.getFileSystemManager().readFile({
        filePath: path,
        encoding: 'base64',
        success: (fileRes) => {
          try {
            wx.getFileSystemManager().unlink({ filePath: path, fail() {} });
          } catch (e) {}
          this._sendAsr(fileRes.data);
        },
        fail: () => {
          try {
            wx.getFileSystemManager().unlink({ filePath: path, fail() {} });
          } catch (e) {}
          this.setData({ translating: false, voiceLabel: '点一下说话' });
          wx.showToast({ title: '这会儿听不清，您打字也行', icon: 'none' });
        },
      });
    });
    this._recorder.onError((err) => {
      this._voiceStarting = false;
      this._clearVoiceMaxTimer();
      this.setData({ recording: false, translating: false, voiceLabel: '点一下说话' });
      const msg = (err && err.errMsg) || '';
      if (msg.indexOf('auth') >= 0) {
        wx.showToast({ title: '没拿到麦克风权限，您打字也行', icon: 'none' });
      } else {
        wx.showToast({ title: '这会儿听不清，您打字也行', icon: 'none' });
      }
    });
  },

  _clearVoiceMaxTimer() {
    if (this._voiceMaxTimer) {
      clearTimeout(this._voiceMaxTimer);
      this._voiceMaxTimer = null;
    }
  },

  async _sendAsr(audioBase64) {
    this.setData({ translating: true, voiceLabel: '正在听…' });
    const res = await request({
      url: '/api/asr',
      method: 'POST',
      data: { audio_base64: audioBase64, format: 'mp3' },
    });
    this.setData({ translating: false, voiceLabel: '点一下说话' });
    if (res.ok && res.data) {
      const text = (res.data.text || '').trim();
      if (text) {
        if (this.data.autoSendVoice) {
          this._startPending(text);
        } else {
          this.setData({ input: text });
        }
      } else {
        wx.showToast({ title: '没听清，您再说一遍或打字', icon: 'none' });
      }
    } else {
      wx.showToast({ title: '这会儿听不清，您打字也行', icon: 'none' });
    }
  },

  onVoiceTap() {
    if (this.data.ended || this.data.translating || !this._recorder) return;
    if (this.data.recording) {
      this._recorder.stop();
      return;
    }
    if (this._voiceStarting) return;
    const startRecording = () => {
      if (this.data.ended || this.data.translating || this.data.recording || this._voiceStarting) return;
      this._ensurePrivacy(() => {
        if (this.data.ended || this.data.recording) return;
        this._stopAudio();
        this._voiceStarting = true;
        this._recorder.start({
          duration: 60000,
          format: 'mp3',
          sampleRate: 16000,
          encodeBitRate: 48000,
          numberOfChannels: 1,
        });
        setTimeout(() => {
          this._voiceStarting = false;
        }, 1000);
      });
    };
    if (!wx.getStorageSync('voice_notice_asr_shown')) {
      if (this._voiceNoticeOpen) return;
      this._voiceNoticeOpen = true;
      wx.showModal({
        title: '提示',
        content: '点一下这个麦克风就能说话，再点一下结束。您说的话会发到云端转成文字，转完就删，不会保存。说完 3 秒会自动帮您发出去，想改就点上面那行字。',
        showCancel: false,
        confirmText: '知道了',
        success: (res) => {
          if (!res.confirm) return;
          wx.setStorageSync('voice_notice_asr_shown', true);
          startRecording();
        },
        complete: () => {
          this._voiceNoticeOpen = false;
        },
      });
      return;
    }
    startRecording();
  },

  // 隐私授权：基础库 2.32 起，麦克风属于隐私接口，没同意前录音会直接失败。
  // app.js 里的 onNeedPrivacyAuthorization 负责弹窗，这里只负责「先要授权再录」。
  _ensurePrivacy(next) {
    if (typeof wx.requirePrivacyAuthorize !== 'function') {
      next();
      return;
    }
    if (this._privacyPending) return;
    this._privacyPending = true;
    wx.requirePrivacyAuthorize({
      success: () => {
        this._privacyPending = false;
        next();
      },
      fail: () => {
        this._privacyPending = false;
        wx.showToast({ title: '同意隐私说明才能用麦克风，打字也行', icon: 'none' });
      },
    });
  },

  _startPending(text) {
    const oldText = this.data.pendingText;
    if (oldText && oldText !== text) {
      const merged = (this.data.input ? this.data.input + '，' : '') + oldText;
      this.setData({ input: merged });
    }
    this._clearPendingTimers();
    this.setData(
      { pendingText: text, pendingCountdown: 3 },
      () => this._measureDock()
    );
    this._pendingTimer = setTimeout(() => this._tickPending(text), 1000);
  },

  _tickPending(text) {
    const left = this.data.pendingCountdown - 1;
    if (left > 0) {
      this.setData({ pendingCountdown: left });
      this._pendingTimer = setTimeout(() => this._tickPending(text), 1000);
      return;
    }
    this._dispatchPending(text);
  },

  _dispatchPending(text) {
    if (!this.data.pendingText || this.data.pendingText !== text) return;
    if (this.data.recording) {
      if (this._pendingRecordDeferred < 3) {
        this._pendingRecordDeferred += 1;
        this._pendingTimer = setTimeout(() => this._dispatchPending(text), 1000);
      } else {
        this._clearPendingTimers();
        this.setData(
          { pendingText: '', pendingCountdown: 0, input: text },
          () => this._measureDock()
        );
        wx.showToast({ title: '先说完，再点发送', icon: 'none' });
      }
      return;
    }
    if (this.data.sending && !this._pendingDeferred) {
      this._pendingDeferred = true;
      this._pendingTimer = setTimeout(() => this._dispatchPending(text), 1000);
      return;
    }
    this._clearPendingTimers();
    if (this.data.sending) {
      this.setData(
        { pendingText: '', pendingCountdown: 0, input: text },
        () => this._measureDock()
      );
      wx.showToast({ title: '还在回复，您改好再发', icon: 'none' });
      return;
    }
    this.setData(
      { pendingText: '', pendingCountdown: 0 },
      () => this._measureDock()
    );
    this.send(text);
  },

  editPending() {
    const text = this.data.pendingText;
    if (!text) return;
    this._clearPendingTimers();
    this.setData(
      { pendingText: '', pendingCountdown: 0, input: text },
      () => this._measureDock()
    );
  },

  _clearPendingTimers() {
    if (this._pendingTimer) {
      clearTimeout(this._pendingTimer);
      this._pendingTimer = null;
    }
    this._pendingDeferred = false;
    this._pendingRecordDeferred = 0;
  },

  _loadVoiceSettings() {
    this.setData({
      autoSendVoice: wx.getStorageSync('auto_send_voice') !== false,
      autoSpeak: wx.getStorageSync('auto_speak') !== false,
      speakSpeed: normalizeSpeakSpeed(wx.getStorageSync('speak_speed')),
    });
  },

  _genThreadId() {
    return 'wx_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  },

  async loadGreeting() {
    if (this._greetingLoading) return;
    // 切 tab 会反复触发 onShow，30 秒内不重复拉画像
    if (Date.now() - (this._greetingFetchedAt || 0) < GREETING_REFRESH_MS) return;
    this._greetingLoading = true;
    this._greetingFetchedAt = Date.now();
    const date = this.formatDate(new Date());
    const greetedKey = 'greeted_' + this.data.thread_id + '_' + date;
    try {
      const profileRes = await request({ url: '/api/memories' });
      if (profileRes.ok && profileRes.data && profileRes.data.profile) {
        const profile = profileRes.data.profile;
        this.setData({ greeting: profile.nickname ? profile.nickname : '您好' });
        this.applyPhraseWall(profile.taboos || []);
      } else {
        this.setData({ greeting: '您好', phraseGroups: PHRASE_GROUPS });
      }
      if (wx.getStorageSync(greetedKey)) return;
      const res = await request({
        url: '/api/greeting?thread_id=' + this.data.thread_id,
      });
      if (res.ok && res.data && res.data.greeting) {
        const uid = 'greet-' + date;
        const messages = this.data.messages.slice();
        if (!messages.some((item) => item.uid === uid)) {
          messages.unshift({
            role: 'assistant',
            content: res.data.greeting,
            ts: Date.now(),
            uid,
          });
          this.setData({
            messages,
            scrollInto: messages.length === 1 ? 'msg-0' : this.data.scrollInto,
          });
          this._persistSoon();
        }
        wx.setStorageSync(greetedKey, true);
      }
    } finally {
      this._greetingLoading = false;
    }
  },

  async loadFamilyNote(force) {
    if (this._loadingFamilyNote) return;
    // onLoad 里已经拉过一次，onShow 紧接着触发时不必再打一次；读完一条要强制刷新
    if (!force && Date.now() - (this._noteFetchedAt || 0) < NOTE_REFRESH_MS) return;
    this._loadingFamilyNote = true;
    this._noteFetchedAt = Date.now();
    try {
      const res = await request({ url: '/api/notes' });
      if (res.ok && res.data) {
        this.setData({ familyNote: res.data.note || null });
      }
    } finally {
      this._loadingFamilyNote = false;
    }
  },

  openFamilyNote() {
    if (!this.data.familyNote) return;
    this.setData({ noteOpen: true });
  },

  async closeFamilyNote() {
    const note = this.data.familyNote;
    if (!note) return;
    this.setData({ noteOpen: false });
    const res = await request({
      url: '/api/notes/' + note.id + '/read',
      method: 'POST',
    });
    if (!res.ok) {
      wx.showToast({ title: '还没记上，再点一次', icon: 'none' });
      return;
    }
    this.setData({ familyNote: null });
    this.loadFamilyNote(true);
  },

  applyPhraseWall(taboos) {
    const list = (taboos || []).filter((t) => t);
    this.setData({
      phraseGroups: PHRASE_GROUPS.map((g) => ({
        title: g.title,
        items: g.items.filter((phrase) => !shouldHidePhrase(phrase, list)),
      })).filter((g) => g.items.length > 0),
    });
  },

  formatDate(d) {
    const m = ('0' + (d.getMonth() + 1)).slice(-2);
    const day = ('0' + d.getDate()).slice(-2);
    return '' + d.getFullYear() + m + day;
  },

  async maybeGreet() {
    await this.loadGreeting();
  },

  onInput(e) {
    this.setData({ input: e.detail.value });
  },

  onSend() {
    const text = this.data.input;
    if (!text || this.data.sending) return;
    this._clearPendingForManualSend();
    this.send(text);
    this.setData({ input: '' });
  },

  onQuick(e) {
    this.onPhrase(e);
  },

  onPhrase(e) {
    if (this.data.sending) return;
    this._clearPendingForManualSend();
    this.send(e.currentTarget.dataset.text);
    if (this.data.wallExpanded) {
      this.setData({ wallExpanded: false });
      setTimeout(() => this._measureDock(), 80);
    }
  },

  dismissNotice() {
    wx.setStorageSync('notice_read', true);
    this.setData({ showNotice: false });
  },

  toggleWall() {
    this.setData({ wallExpanded: !this.data.wallExpanded });
    setTimeout(() => this._measureDock(), 80);
  },

  // 窗口信息只取一次；wx.getSystemInfoSync 已废弃，优先用 wx.getWindowInfo
  _windowMetrics() {
    if (this._metrics) return this._metrics;
    let info = null;
    try {
      info = typeof wx.getWindowInfo === 'function' ? wx.getWindowInfo() : wx.getSystemInfoSync();
    } catch (err) {
      info = null;
    }
    const width = (info && info.windowWidth) || 375;
    const screenHeight = (info && (info.screenHeight || info.windowHeight)) || 667;
    const safeArea = info && info.safeArea;
    this._metrics = {
      tabBarPx: 112 * (width / 750),
      safePx: safeArea ? Math.max(0, screenHeight - safeArea.bottom) : 0,
    };
    return this._metrics;
  },

  _measureDock() {
    wx.createSelectorQuery()
      .in(this)
      .select('.dock')
      .boundingClientRect((rect) => {
        if (!rect || !rect.height) return;
        const metrics = this._windowMetrics();
        const dockHeight =
          Math.ceil(rect.height) + 12 + Math.ceil(metrics.tabBarPx + metrics.safePx);
        // 高度没变就不触发渲染
        if (dockHeight !== this.data.dockHeight) this.setData({ dockHeight });
      })
      .exec();
  },

  _initAudio() {
    if (typeof wx.createInnerAudioContext !== 'function') return;
    const audio = wx.createInnerAudioContext();
    audio.obeyMuteSwitch = false;
    audio.onError(() => this._ttsUnavailable('transient'));
    this._audio = audio;
  },

  _stopAudio() {
    this._speakSerial = (this._speakSerial || 0) + 1;
    if (!this._audio) return;
    try {
      this._audio.stop();
    } catch (err) {}
  },

  _ttsUnavailable(kind) {
    if (kind !== 'config') return;
    this._ttsDisabled = true;
  },

  // 走统一封装：离线直接失败、401 会跳登录，不再自己拼 url 和 header
  _ttsRequest(text, speed) {
    return request({
      url: '/api/tts',
      method: 'POST',
      data: { text, speed },
      responseType: 'arraybuffer',
      timeout: 15000,
    }).then((res) => {
      if (res.ok) {
        const buffer = res.data;
        if (buffer && typeof buffer.byteLength === 'number' && buffer.byteLength > 0) {
          this._ttsDisabled = false;
          return { buffer };
        }
        return { kind: 'transient' };
      }
      if (res.status === 501 || res.status === 503) return { kind: 'config' };
      return { kind: 'transient' };
    });
  },

  _ttsHash(text, speed) {
    const source = text + '|' + speed;
    let hash = 2166136261;
    for (let i = 0; i < source.length; i += 1) {
      hash ^= source.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16);
  },

  _cachedTts(filePath) {
    try {
      const stat = wx.getFileSystemManager().statSync(filePath);
      return !!(stat && stat.size > 100);
    } catch (err) {
      return false;
    }
  },

  _playTtsFile(filePath, serial) {
    if (serial !== this._speakSerial || !this._audio) return;
    try {
      this._audio.stop();
      this._audio.src = filePath;
      this._audio.play();
    } catch (err) {
      this._ttsUnavailable('transient');
    }
  },

  async _speak(text) {
    const clean = (text || '').trim();
    if (!clean || !this._audio || this._ttsDisabled) return;
    if (!wx.env || !wx.env.USER_DATA_PATH) return;
    const punctuation = Math.max(clean.lastIndexOf('。', 119), clean.lastIndexOf('，', 119));
    const spoken = punctuation >= 0 ? clean.slice(0, punctuation + 1) : clean.slice(0, 120);
    this._stopAudio();
    const serial = this._speakSerial;
    // 语速 0 是合法值（正常），不能用 || 兜底，否则会被当成缺失而变成 1.0
    const speed =
      typeof this.data.speakSpeed === 'number' ? this.data.speakSpeed : DEFAULT_SPEAK_SPEED;
    const filePath = wx.env.USER_DATA_PATH + '/tts_cache_' + this._ttsHash(spoken, speed) + '.mp3';
    // 同一句话重复点播时直接播本地缓存，不再打网络
    if (this._cachedTts(filePath)) {
      this._playTtsFile(filePath, serial);
      return;
    }
    const result = await this._ttsRequest(spoken, speed);
    if (serial !== this._speakSerial) return;
    if (result.kind === 'config') {
      this._ttsUnavailable('config');
      return;
    }
    if (!result.buffer) {
      this._ttsUnavailable('transient');
      return;
    }
    try {
      wx.getFileSystemManager().writeFile({
        filePath,
        data: result.buffer,
        success: () => this._playTtsFile(filePath, serial),
        fail: () => {
          if (serial === this._speakSerial) this._ttsUnavailable('transient');
        },
      });
    } catch (err) {
      if (serial === this._speakSerial) this._ttsUnavailable('transient');
    }
  },

  onSpeak(e) {
    if (e.currentTarget.dataset.pending) return;
    this._speak(e.currentTarget.dataset.text);
  },

  _clearPendingForManualSend() {
    const hadPending = !!this.data.pendingText;
    this._clearPendingTimers();
    if (!hadPending) return;
    this.setData(
      { pendingText: '', pendingCountdown: 0 },
      () => this._measureDock()
    );
  },

  _ab2str(buffer) {
    const bytes = new Uint8Array(buffer);
    let out = '';
    let i = 0;
    while (i < bytes.length) {
      const b = bytes[i];
      let len = 1;
      let cp = 0;
      if (b < 0x80) {
        cp = b;
      } else if ((b & 0xe0) === 0xc0) {
        len = 2;
        cp = b & 0x1f;
      } else if ((b & 0xf0) === 0xe0) {
        len = 3;
        cp = b & 0x0f;
      } else if ((b & 0xf8) === 0xf0) {
        len = 4;
        cp = b & 0x07;
      } else {
        i += 1;
        continue;
      }
      if (i + len > bytes.length) {
        return { text: out, rest: Array.from(bytes.slice(i)) };
      }
      for (let j = 1; j < len; j++) {
        cp = (cp << 6) | (bytes[i + j] & 0x3f);
      }
      out += String.fromCodePoint(cp);
      i += len;
    }
    return { text: out, rest: [] };
  },

  _parseSseBlock(block) {
    let event = null;
    let data = null;
    block.split('\n').forEach((line) => {
      if (line.indexOf('event: ') === 0) {
        event = line.slice(7).trim();
      } else if (line.indexOf('data: ') === 0) {
        try {
          data = JSON.parse(line.slice(6).trim());
        } catch (err) {
          data = null;
        }
      }
    });
    if (!event) return null;
    return { event, data: data || {} };
  },

  _streamRequest(data, uid) {
    return new Promise((resolve) => {
      let settled = false;
      let acc = '';
      let action = 'reply';
      let params = null;
      let buf = '';
      let task = null;
      let noChunkTimer = null;
      let restBytes = [];
      let decoder = null;
      if (typeof TextDecoder !== 'undefined') {
        try {
          decoder = new TextDecoder('utf-8');
        } catch (err) {
          decoder = null;
        }
      }

      // 流式增量按 80ms 合并一次，避免每个分片都触发一次 setData
      let patchTimer = null;
      let patchDirty = false;
      const flushPatch = () => {
        if (patchTimer) {
          clearTimeout(patchTimer);
          patchTimer = null;
        }
        if (!patchDirty) return;
        patchDirty = false;
        this._patchPendingByUid(uid, { content: acc || '正在回复…' });
      };
      const markPatch = () => {
        patchDirty = true;
        if (patchTimer) return;
        patchTimer = setTimeout(() => {
          patchTimer = null;
          flushPatch();
        }, 80);
      };

      const processBlocks = () => {
        let idx;
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const block = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          const parsed = this._parseSseBlock(block);
          if (!parsed) continue;
          if (parsed.event === 'meta') {
            action = parsed.data.action || 'reply';
            params = parsed.data.params || null;
          } else if (parsed.event === 'delta') {
            acc += parsed.data.text || '';
            markPatch();
          } else if (parsed.event === 'done') {
            finish({ streamed: true, action, reply_text: acc, params });
          }
        }
      };

      const decodeChunk = (buffer) => {
        if (decoder) {
          return decoder.decode(buffer, { stream: true });
        }
        const bytes = new Uint8Array(buffer);
        const combined = new Uint8Array(restBytes.length + bytes.length);
        combined.set(restBytes, 0);
        combined.set(bytes, restBytes.length);
        const r = this._ab2str(combined.buffer);
        restBytes = r.rest;
        return r.text;
      };

      const clearNoChunkTimer = () => {
        if (noChunkTimer) {
          clearTimeout(noChunkTimer);
          noChunkTimer = null;
        }
      };

      const resetNoChunkTimer = () => {
        clearNoChunkTimer();
        noChunkTimer = setTimeout(() => {
          console.warn('流式 15 秒无数据，降级到非流式');
          if (task && task.abort) task.abort();
          finish({ fallback: true });
        }, 15000);
      };

      const finish = (result) => {
        if (settled) return;
        settled = true;
        clearNoChunkTimer();
        if (patchTimer) {
          clearTimeout(patchTimer);
          patchTimer = null;
        }
        if (decoder) {
          const tail = decoder.decode();
          if (tail) {
            buf += tail;
            processBlocks();
          }
        }
        resolve(result);
      };

      resetNoChunkTimer();

      task = wx.request({
        url: config.baseUrl() + '/api/chat/stream',
        method: 'POST',
        data: data,
        enableChunked: true,
        header: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + (wx.getStorageSync('token') || ''),
        },
        success: (res) => {
          // 非 2xx 的响应体是 JSON 错误，不会带 delta，直接走非流式兜底，
          // 让统一的 request 封装去处理 401 / 业务提示
          if (res && res.statusCode && (res.statusCode < 200 || res.statusCode >= 300)) {
            finish({ fallback: true });
            return;
          }
          if (acc) {
            finish({ streamed: true, action, reply_text: acc, params });
          } else {
            finish({ fallback: true });
          }
        },
        fail: (err) => {
          console.warn('流式请求失败，降级到非流式', err.errMsg);
          finish({ fallback: true });
        },
      });

      if (!task || typeof task.onChunkReceived !== 'function') {
        console.warn('基础库不支持 enableChunked，降级到非流式');
        finish({ fallback: true });
        return;
      }

      task.onChunkReceived((res) => {
        resetNoChunkTimer();
        buf += decodeChunk(res.data);
        processBlocks();
      });
    });
  },

  async send(rawText) {
    const text = (rawText || '').trim();
    if (!text || this.data.ended || this.data.sending) return;

    const base = 'm' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    // 问和答用两个 uid，保证列表 key 唯一，追加时只复用新增节点
    const userUid = base + 'q';
    const replyUid = base + 'r';
    this._active = (this._active || 0) + 1;
    this.setData({ sending: true });
    const messages = this._trim(
      this.data.messages.concat([
        { role: 'user', content: text, ts: Date.now(), uid: userUid },
        { role: 'assistant', pending: true, content: '正在回复…', ts: Date.now(), uid: replyUid },
      ])
    );
    this.setData({ messages, scrollInto: 'msg-' + (messages.length - 1) });

    const streamRes = await this._streamRequest({ thread_id: this.data.thread_id, text }, replyUid);

    let action;
    let params = null;
    if (streamRes.streamed) {
      const reply = normalizeReply(streamRes.reply_text);
      const replyIndex = this._patchPendingByUid(replyUid, { content: reply, pending: false, ts: Date.now() });
      if (replyIndex >= 0) {
        this.setData({ scrollInto: 'msg-' + replyIndex });
        if (this.data.autoSpeak) this._speak(reply);
      }
      action = streamRes.action;
      params = streamRes.params;
    } else {
      const timeoutId = setTimeout(() => {
        this._patchPendingByUid(replyUid, { content: '还没等到回复，再等等' });
      }, REPLY_TIMEOUT_MS);

      const res = await request({
        url: '/api/chat',
        method: 'POST',
        data: { thread_id: this.data.thread_id, text },
      });

      clearTimeout(timeoutId);

      if (!res.ok) {
        if (res.kind === 'business' && res.msg) {
          wx.showToast({ title: res.msg, icon: 'none' });
        }
        this._markFailedByUid(userUid, replyUid);
        this._active = Math.max(0, (this._active || 0) - 1);
        this.setData({ sending: this._active > 0 });
        return;
      }
      const reply = normalizeReply(res.data && res.data.reply_text);
      const replyIndex = this._patchPendingByUid(replyUid, { content: reply, pending: false, ts: Date.now() });
      if (replyIndex >= 0) {
        this.setData({ scrollInto: 'msg-' + replyIndex });
        if (this.data.autoSpeak) this._speak(reply);
      }
      action = res.data.action;
      params = res.data.params || null;
    }

    if (action === 'end') {
      this._enterEnd();
    } else if (action === 'start_game') {
      const p = params || {};
      setTimeout(() => {
        getApp().globalData.pendingGame = {
          game_type: p.game_type || 'memory_box',
          difficulty: p.difficulty || 0,
        };
        wx.switchTab({ url: '/pages/game/game' });
      }, 600);
    }
    this._persistSoon();

    this._active = Math.max(0, (this._active || 0) - 1);
    this.setData({ sending: this._active > 0 });
  },

  retry(e) {
    if (this.data.ended) return;
    const uid = e.currentTarget.dataset.uid;
    const index = this.data.messages.findIndex((m) => m.uid === uid && m.failed);
    if (index < 0) return;
    const text = this.data.messages[index].content;
    const msgs = this.data.messages.slice();
    msgs.splice(index, 1);
    this.setData({ messages: msgs });
    this.send(text);
  },

  _patchPendingByUid(uid, patch) {
    const index = this.data.messages.findIndex((m) => m.uid === uid && m.pending);
    if (index < 0) return -1;
    const updates = {};
    Object.keys(patch).forEach((k) => {
      updates['messages[' + index + '].' + k] = patch[k];
    });
    this.setData(updates);
    return index;
  },

  _markFailedByUid(userUid, replyUid) {
    const msgs = this.data.messages.slice();
    const userIndex = msgs.findIndex((m) => m.uid === userUid);
    if (userIndex >= 0) {
      msgs[userIndex] = Object.assign({}, msgs[userIndex], { failed: true });
    }
    const pendingIndex = msgs.findIndex((m) => m.uid === replyUid);
    if (pendingIndex >= 0) {
      msgs.splice(pendingIndex, 1);
    }
    this.setData({ messages: msgs });
    this._persistSoon();
  },

  // 长会话裁剪：只留最近 MAX_MESSAGES 条，老消息仍在后端与本地落盘里
  _trim(messages) {
    if (messages.length <= MAX_MESSAGES) return messages;
    return messages.slice(messages.length - MAX_MESSAGES);
  },

  _cancelPersist() {
    if (this._persistTimer) {
      clearTimeout(this._persistTimer);
      this._persistTimer = null;
    }
  },

  _persist() {
    if (this._persistTimer) {
      clearTimeout(this._persistTimer);
      this._persistTimer = null;
    }
    const records = this.data.messages
      .filter((m) => m.content && m.role !== 'system' && !m.pending && !m.failed)
      .map((m) => ({
        role: m.role,
        content: m.content,
        ts: m.ts || Date.now(),
        uid: m.uid || '',
      }));
    try {
      wx.setStorageSync('chat_history_' + this.data.thread_id, records.slice(-50));
    } catch (err) {
      console.error('保存聊天记录失败：', err);
    }
  },

  // setStorageSync 会阻塞渲染线程，连续收发时合并成一次落盘
  _persistSoon() {
    if (this._persistTimer) return;
    this._persistTimer = setTimeout(() => {
      this._persistTimer = null;
      this._persist();
    }, 600);
  },

  _enterEnd() {
    if (this.data.ended) return;
    const messages = this.data.messages.concat([
      { role: 'system', system: true, content: '这轮聊完了', uid: 'end' + Date.now() },
    ]);
    this.setData({ messages, ended: true, scrollInto: 'msg-' + (messages.length - 1) });
  },

  restart() {
    this._clearPendingTimers();
    this._stopAudio();
    this._cancelPersist();
    wx.removeStorageSync('chat_history_' + this.data.thread_id);
    this.setData({ messages: [], ended: false, input: '', pendingText: '', pendingCountdown: 0 });
    this._resetThread();
  },

  clearChat() {
    wx.showModal({
      title: '提示',
      content: '确定要清空这段对话吗',
      confirmText: '清空',
      cancelText: '再想想',
      success: (r) => {
        if (r.confirm) {
          this._clearPendingTimers();
          this._stopAudio();
          this._cancelPersist();
          wx.removeStorageSync('chat_history_' + this.data.thread_id);
          this.setData({ messages: [], ended: false, input: '', pendingText: '', pendingCountdown: 0 });
          this._resetThread();
        }
      },
    });
  },

  logout() {
    wx.showModal({
      title: '提示',
      content: '确定要退出登录吗',
      confirmText: '退出',
      cancelText: '再想想',
      success: (r) => {
        if (!r.confirm) return;
        this._clearPendingTimers();
        this._stopAudio();
        clearElderSession();
        wx.reLaunch({ url: '/pages/login/login' });
      },
    });
  },

  _resetThread() {
    const threadId = this._genThreadId();
    wx.setStorageSync('thread_id', threadId);
    this.setData({ thread_id: threadId });
  },

  goMemory() {
    wx.navigateTo({ url: '/pages/memory/memory' });
  },

  goGame() {
    getApp().globalData.showGameMenu = true;
    wx.switchTab({ url: '/pages/game/game' });
  },
});
