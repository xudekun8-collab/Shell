const { request } = require('../../utils/request.js');
const config = require('../../utils/config.js');
const { PHRASE_GROUPS, QUICK_PHRASES } = require('../../utils/constants.js');
const { getUserId } = require('../../utils/user.js');
const { shouldHidePhrase } = require('../../utils/taboo.js');
const REPLY_TIMEOUT_MS = 8000;

function normalizeReply(text) {
  const s = (text || '').trim();
  if (!s) return '我这儿没听清，您再说一遍';
  if (s.length <= 300) return s;
  const head = s.slice(0, 300);
  const cut = Math.max(
    head.lastIndexOf('。'),
    head.lastIndexOf('？'),
    head.lastIndexOf('！'),
    head.lastIndexOf('?'),
    head.lastIndexOf('!'),
    head.lastIndexOf('.')
  );
  return cut > 150 ? s.slice(0, cut + 1) : head;
}

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
    voiceLabel: '按住说话',
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
    const restored = Array.isArray(history) ? history : [];
    this.setData({
      user_id: getUserId(),
      thread_id: threadId,
      messages: restored,
      scrollInto: restored.length ? 'msg-' + (restored.length - 1) : '',
      showNotice: !wx.getStorageSync('notice_read'),
    });
    this.loadGreeting();
    this._initRecorder();
  },

  onReady() {
    this._measureDock();
  },

  onShow() {
    this.maybeGreet();
    this._measureDock();
  },

  _initRecorder() {
    this._recorder = wx.getRecorderManager();
    this._recorder.onStart(() => {
      this.setData({ recording: true, voiceLabel: '松开结束' });
    });
    this._recorder.onStop((res) => {
      this.setData({ recording: false, translating: true, voiceLabel: '正在听…' });
      const dur = res && res.duration ? res.duration : 0;
      if (dur < 1000) {
        this.setData({ translating: false, voiceLabel: '按住说话' });
        wx.showToast({ title: '太短了，您多说两句', icon: 'none' });
        return;
      }
      const path = res && res.tempFilePath;
      if (!path) {
        this.setData({ translating: false, voiceLabel: '按住说话' });
        wx.showToast({ title: '这会儿听不清，您打字也行', icon: 'none' });
        return;
      }
      wx.getFileSystemManager().readFile({
        filePath: path,
        encoding: 'base64',
        success: (fileRes) => this._sendAsr(fileRes.data),
        fail: () => {
          this.setData({ translating: false, voiceLabel: '按住说话' });
          wx.showToast({ title: '这会儿听不清，您打字也行', icon: 'none' });
        },
      });
    });
    this._recorder.onError((err) => {
      this.setData({ recording: false, translating: false, voiceLabel: '按住说话' });
      const msg = (err && err.errMsg) || '';
      if (msg.indexOf('auth') >= 0) {
        wx.showToast({ title: '没拿到麦克风权限，您打字也行', icon: 'none' });
      } else {
        wx.showToast({ title: '这会儿听不清，您打字也行', icon: 'none' });
      }
    });
  },

  async _sendAsr(audioBase64) {
    this.setData({ translating: true, voiceLabel: '正在听…' });
    const res = await request({
      url: '/api/asr',
      method: 'POST',
      data: { audio_base64: audioBase64, format: 'mp3' },
    });
    this.setData({ translating: false, voiceLabel: '按住说话' });
    if (res.ok && res.data) {
      const text = (res.data.text || '').trim();
      if (text) {
        this.setData({ input: text });
      } else {
        wx.showToast({ title: '没听清，您再说一遍或打字', icon: 'none' });
      }
    } else {
      wx.showToast({ title: '这会儿听不清，您打字也行', icon: 'none' });
    }
  },

  onVoiceStart() {
    if (this.data.ended || this.data.recording || this.data.translating) return;
    if (!wx.getStorageSync('voice_notice_asr_shown')) {
      wx.setStorageSync('voice_notice_asr_shown', true);
      wx.showModal({
        title: '提示',
        content: '按住说话，录音会发到云端转成文字，转完就删，不会保存。您看一眼再点发送。',
        showCancel: false,
        confirmText: '知道了',
      });
      return;
    }
    this._recorder.start({
      duration: 60000,
      format: 'mp3',
      sampleRate: 16000,
      encodeBitRate: 48000,
      numberOfChannels: 1,
    });
  },

  onVoiceEnd() {
    if (!this.data.recording || !this._recorder) return;
    this._recorder.stop();
  },

  _genThreadId() {
    return 'wx_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  },

  async loadGreeting() {
    const res = await request({ url: '/api/memories' });
    if (res.ok && res.data && res.data.profile) {
      const profile = res.data.profile;
      this.setData({ greeting: profile.nickname ? profile.nickname : '您好' });
      this.applyPhraseWall(profile.taboos || []);
    } else {
      this.setData({ greeting: '您好', phraseGroups: PHRASE_GROUPS });
    }
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
    if (this.data.messages.length > 0) return;
    const res = await request({ url: '/api/greeting?thread_id=' + this.data.thread_id });
    if (!res.ok || !res.data || !res.data.greeting) return;
    const key = 'greeting_' + this.formatDate(new Date()) + '_' + res.data.period;
    if (wx.getStorageSync(key)) return;
    wx.setStorageSync(key, true);
    this.setData({ messages: [{ role: 'assistant', content: res.data.greeting, ts: Date.now() }] });
    this._persist();
  },

  onInput(e) {
    this.setData({ input: e.detail.value });
  },

  onSend() {
    const text = this.data.input;
    this.send(text);
    this.setData({ input: '' });
  },

  onQuick(e) {
    this.send(e.currentTarget.dataset.text);
  },

  onPhrase(e) {
    this.send(e.currentTarget.dataset.text);
  },

  dismissNotice() {
    wx.setStorageSync('notice_read', true);
    this.setData({ showNotice: false });
  },

  toggleWall() {
    this.setData({ wallExpanded: !this.data.wallExpanded });
    setTimeout(() => this._measureDock(), 80);
  },

  _measureDock() {
    wx.createSelectorQuery()
      .in(this)
      .select('.dock')
      .boundingClientRect((rect) => {
        if (rect && rect.height) {
          this.setData({ dockHeight: Math.ceil(rect.height) + 12 });
        }
      })
      .exec();
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
            this._patchPendingByUid(uid, { content: acc || '正在回复…' });
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
        url: config.base_url + '/api/chat/stream',
        method: 'POST',
        data: data,
        enableChunked: true,
        header: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + (wx.getStorageSync('token') || ''),
        },
        success: () => {
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
    if (!text || this.data.ended) return;

    const uid = 'm' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    this._active = (this._active || 0) + 1;
    this.setData({ sending: true });
    const messages = this.data.messages.concat([
      { role: 'user', content: text, ts: Date.now(), uid },
      { role: 'assistant', pending: true, content: '正在回复…', uid },
    ]);
    this.setData({ messages, scrollInto: 'msg-' + (messages.length - 1) });

    const streamRes = await this._streamRequest({ thread_id: this.data.thread_id, text }, uid);

    let action;
    let params = null;
    if (streamRes.streamed) {
      const reply = normalizeReply(streamRes.reply_text);
      const replyIndex = this._patchPendingByUid(uid, { content: reply, pending: false, ts: Date.now() });
      if (replyIndex >= 0) {
        this.setData({ scrollInto: 'msg-' + replyIndex });
      }
      action = streamRes.action;
      params = streamRes.params;
    } else {
      const timeoutId = setTimeout(() => {
        this._patchPendingByUid(uid, { content: '还没等到回复，再等等' });
      }, REPLY_TIMEOUT_MS);

      const res = await request({
        url: '/api/chat',
        method: 'POST',
        data: { thread_id: this.data.thread_id, text },
      });

      clearTimeout(timeoutId);

      if (!res.ok) {
        this._markFailedByUid(uid);
        this._active = Math.max(0, (this._active || 0) - 1);
        this.setData({ sending: this._active > 0 });
        return;
      }
      const reply = normalizeReply(res.data && res.data.reply_text);
      const replyIndex = this._patchPendingByUid(uid, { content: reply, pending: false, ts: Date.now() });
      if (replyIndex >= 0) {
        this.setData({ scrollInto: 'msg-' + replyIndex });
      }
      action = res.data.action;
      params = res.data.params || null;
    }

    if (action === 'end') {
      this._enterEnd();
    } else if (action === 'start_game') {
      const p = params || {};
      setTimeout(() => {
        wx.navigateTo({
          url: '/pages/game/game?game_type=' + (p.game_type || 'memory_box') + '&difficulty=' + (p.difficulty || 0),
        });
      }, 600);
    }
    this._persist();

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

  _markFailedByUid(uid) {
    const msgs = this.data.messages.slice();
    const userIndex = msgs.findIndex((m) => m.uid === uid && m.role === 'user');
    if (userIndex >= 0) {
      msgs[userIndex] = Object.assign({}, msgs[userIndex], { failed: true });
    }
    const pendingIndex = msgs.findIndex((m) => m.uid === uid && m.pending);
    if (pendingIndex >= 0) {
      msgs.splice(pendingIndex, 1);
    }
    this.setData({ messages: msgs });
    this._persist();
  },

  _persist() {
    const records = this.data.messages
      .filter((m) => m.content && m.role !== 'system' && !m.pending && !m.failed)
      .map((m) => ({ role: m.role, content: m.content, ts: m.ts || Date.now() }));
    wx.setStorageSync('chat_history_' + this.data.thread_id, records.slice(-50));
  },

  _enterEnd() {
    if (this.data.ended) return;
    const messages = this.data.messages.concat([
      { role: 'system', system: true, content: '这轮聊完了' },
    ]);
    this.setData({ messages, ended: true, scrollInto: 'msg-' + (messages.length - 1) });
  },

  restart() {
    wx.removeStorageSync('chat_history_' + this.data.thread_id);
    this.setData({ messages: [], ended: false, input: '' });
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
          wx.removeStorageSync('chat_history_' + this.data.thread_id);
          this.setData({ messages: [], ended: false, input: '' });
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
        wx.removeStorageSync('token');
        wx.removeStorageSync('user_id');
        wx.removeStorageSync('thread_id');
        try {
          const info = wx.getStorageInfoSync();
          (info.keys || []).forEach((key) => {
            if (key.indexOf('chat_history_') === 0) {
              wx.removeStorageSync(key);
            }
          });
        } catch (err) {
          console.error('清空聊天缓存失败：', err);
        }
        wx.redirectTo({ url: '/pages/login/login' });
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
    wx.navigateTo({ url: '/pages/game/game' });
  },
});
