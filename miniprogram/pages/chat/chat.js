const { request } = require('../../utils/request.js');
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
  },

  onReady() {
    this._measureDock();
  },

  onShow() {
    this.maybeGreet();
    this._measureDock();
  },

  _genThreadId() {
    return 'wx_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
  },

  async loadGreeting() {
    const res = await request({ url: '/api/memories/' + this.data.user_id });
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
    const res = await request({ url: '/api/greeting/' + this.data.user_id + '?thread_id=' + this.data.thread_id });
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

    const timeoutId = setTimeout(() => {
      this._patchPendingByUid(uid, { content: '还没等到回复，再等等' });
    }, REPLY_TIMEOUT_MS);

    const res = await request({
      url: '/api/chat',
      method: 'POST',
      data: { user_id: this.data.user_id, thread_id: this.data.thread_id, text },
    });

    clearTimeout(timeoutId);

    if (res.ok) {
      const reply = normalizeReply(res.data && res.data.reply_text);
      const replyIndex = this._patchPendingByUid(uid, { content: reply, pending: false, ts: Date.now() });
      if (replyIndex >= 0) {
        this.setData({ scrollInto: 'msg-' + replyIndex });
      }
      if (res.data.action === 'end') {
        this._enterEnd();
      } else if (res.data.action === 'start_game') {
        const params = res.data.params || {};
        setTimeout(() => {
          wx.navigateTo({
            url: '/pages/game/game?game_type=' + (params.game_type || 'memory_box') + '&difficulty=' + (params.difficulty || 0),
          });
        }, 600);
      }
      this._persist();
    } else {
      this._markFailedByUid(uid);
    }

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
