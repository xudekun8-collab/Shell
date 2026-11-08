const { request } = require('../../utils/request.js');

Page({
  data: {
    user_id: 'demo_user_1',
    thread_id: '',
    greeting: '您好',
    messages: [],
    input: '',
    sending: false,
    scrollInto: '',
    quickTexts: [
      { label: '再说一遍', text: '再说一遍' },
      { label: '慢一点', text: '慢一点' },
      { label: '结束', text: '不聊了' },
    ],
  },

  onLoad() {
    let threadId = wx.getStorageSync('thread_id');
    if (!threadId) {
      threadId = 'wx_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
      wx.setStorageSync('thread_id', threadId);
    }
    this.setData({ thread_id: threadId });
    this.loadGreeting();
  },

  async loadGreeting() {
    const res = await request({ url: '/api/memories/' + this.data.user_id });
    if (res.ok && res.data && res.data.profile && res.data.profile.nickname) {
      this.setData({ greeting: res.data.profile.nickname + '，您好' });
    } else {
      this.setData({ greeting: '您好' });
    }
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
      wx.showToast({ title: '网络不太顺畅，再试一次', icon: 'none' });
    }
    this.setData({ sending: false });
  },

  onVoice() {
    wx.showToast({ title: '语音功能暂未开放', icon: 'none' });
  },

  goMemory() {
    wx.navigateTo({ url: '/pages/memory/memory' });
  },

  goGame() {
    wx.navigateTo({ url: '/pages/game/game' });
  },
});
