const { request } = require('../../utils/request.js');

Page({
  data: {
    user_id: 'demo_user_1',
    profile: null,
    events: [],
    sessions: [],
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
      this.setData({
        profile: profile,
        events: res.data.events || [],
        sessions: res.data.sessions || [],
      });
    } else {
      wx.showToast({ title: '网络不太顺畅，再试一次', icon: 'none' });
    }
  },

  onDelete(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '提示',
      content: '删除后我就不会再记得这件事了，确定吗',
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
            wx.showToast({ title: '删除失败，再试一次', icon: 'none' });
          }
        }
      },
    });
  },
});
