const { request } = require('../../utils/request.js');

Page({
  data: {
    user_id: 'demo_user_1',
    profile: null,
    events: [],
    eventsShown: [],
    eventsRemainder: 0,
    eventsExpanded: false,
    sessions: [],
    showDetail: false,
  },

  onShow() {
    this.fetch();
  },

  async fetch() {
    const res = await request({ url: '/api/memories/' + this.data.user_id });
    if (res.ok && res.data) {
      const profile = res.data.profile || null;
      if (profile) {
        profile.interests_text = (profile.interests || []).join('、');
        profile.taboos_text = (profile.taboos || []).join('、');
      }
      const events = (res.data.events || []).map((e) => ({
        memory_id: e.memory_id,
        content: (e.content || '').replace(/我(?!们)/g, '您'),
      }));
      const sessions = (res.data.sessions || [])
        .map((s) => ({ content: (s.content || '').trim() }))
        .filter((s) => s.content);
      this.setData({
        profile: profile,
        events: events,
        eventsShown: events.slice(0, 5),
        eventsRemainder: Math.max(0, events.length - 5),
        eventsExpanded: false,
        sessions: sessions,
      });
    } else {
      wx.showToast({ title: '我这儿信号有点弱，咱们等会儿再说。', icon: 'none' });
    }
  },

  toggleDetail() {
    this.setData({ showDetail: !this.data.showDetail });
  },

  toggleEvents() {
    if (this.data.eventsExpanded) {
      this.setData({ eventsShown: this.data.events.slice(0, 5), eventsExpanded: false });
    } else {
      this.setData({ eventsShown: this.data.events, eventsExpanded: true });
    }
  },

  onDelete(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '提示',
      content: '这条我就忘掉啦，确定吗？',
      confirmText: '删除',
      cancelText: '再想想',
      success: async (r) => {
        if (r.confirm) {
          const res = await request({
            url: '/api/memories/' + this.data.user_id + '/' + id,
            method: 'DELETE',
          });
          if (res.ok) {
            wx.showToast({ title: '已删除', icon: 'none' });
            this.fetch();
          } else {
            wx.showToast({ title: '我这儿信号有点弱，咱们等会儿再说。', icon: 'none' });
          }
        }
      },
    });
  },
});
