const { request } = require('../../utils/request.js');

const PHRASE_GROUPS = [
  { title: '身上', items: ['我昨晚没睡好', '今天身上不太舒服', '我吃过了', '该吃药了'] },
  { title: '家里人', items: ['我孙女快来看我了', '我想我儿子了', '今天孙子给我打电话了', '我老伴以前爱唱戏'] },
  { title: '日常', items: ['今天天气不错', '我下楼走了一圈', '咱们聊会儿', '陪我玩个游戏'] },
];

const QUICK_PHRASES = ['我吃过了', '今天身上不太舒服', '咱们聊会儿', '陪我玩个游戏'];

Page({
  data: {
    user_id: 'demo_user_1',
    thread_id: '',
    greeting: '您好',
    messages: [],
    input: '',
    sending: false,
    scrollInto: '',
    showNotice: false,
    wallExpanded: false,
    quickPhrases: QUICK_PHRASES,
    quickTexts: [
      { label: '再说一遍', text: '再说一遍' },
      { label: '慢一点', text: '慢一点' },
      { label: '结束', text: '不聊了' },
    ],
    phraseGroups: PHRASE_GROUPS,
  },

  onLoad() {
    let threadId = wx.getStorageSync('thread_id');
    if (!threadId) {
      threadId = 'wx_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
      wx.setStorageSync('thread_id', threadId);
    }
    this.setData({ thread_id: threadId });
    this.setData({ showNotice: !wx.getStorageSync('notice_read') });
    this.loadGreeting();
  },

  onShow() {
    this.maybeGreet();
  },

  async loadGreeting() {
    const res = await request({ url: '/api/memories/' + this.data.user_id });
    if (res.ok && res.data && res.data.profile) {
      const profile = res.data.profile;
      this.setData({ greeting: profile.nickname ? profile.nickname + '，您好' : '您好' });
      this.applyPhraseWall(profile.taboos || []);
    } else {
      this.setData({ greeting: '您好', phraseGroups: PHRASE_GROUPS });
    }
  },

  applyPhraseWall(taboos) {
    const hideLaoban = taboos.some((t) => t.indexOf('老伴') >= 0);
    if (!hideLaoban) {
      this.setData({ phraseGroups: PHRASE_GROUPS });
      return;
    }
    this.setData({
      phraseGroups: PHRASE_GROUPS.map((g) => ({
        title: g.title,
        items: g.items.filter((t) => t !== '我老伴以前爱唱戏'),
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
    this.setData({ messages: [{ role: 'assistant', content: res.data.greeting }] });
  },

  onInput(e) {
    this.setData({ input: e.detail.value });
  },

  onSend() {
    this.send(this.data.input);
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
  },

  async send(rawText) {
    const text = (rawText || '').trim();
    if (!text || this.data.sending) return;

    this.setData({ input: '', sending: true });
    const messages = this.data.messages.concat({ role: 'user', content: text });
    this.setData({ messages: messages, scrollInto: 'msg-' + (messages.length - 1) });

    const res = await request({
      url: '/api/chat',
      method: 'POST',
      data: { user_id: this.data.user_id, thread_id: this.data.thread_id, text: text },
    });

    if (res.ok) {
      const next = this.data.messages.concat({ role: 'assistant', content: res.data.reply_text });
      this.setData({ messages: next, scrollInto: 'msg-' + (next.length - 1) });
      if (res.data.action === 'start_game') {
        const params = res.data.params || {};
        setTimeout(() => {
          wx.navigateTo({
            url: '/pages/game/game?game_type=' + (params.game_type || 'memory_box') + '&difficulty=' + (params.difficulty || 0),
          });
        }, 600);
      }
    } else {
      wx.showToast({ title: '我这儿信号有点弱，咱们等会儿再说。', icon: 'none' });
    }
    this.setData({ sending: false });
  },

  goMemory() {
    wx.navigateTo({ url: '/pages/memory/memory' });
  },

  goGame() {
    wx.navigateTo({ url: '/pages/game/game' });
  },
});
