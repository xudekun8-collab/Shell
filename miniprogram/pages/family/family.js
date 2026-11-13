const config = require('../../utils/config.js');

const GAME_TYPE_TEXT = { memory_box: '记东西', category_sort: '分分类' };

function token() {
  return wx.getStorageSync('family_token') || '';
}

Page({
  data: {
    bound: false,
    code: '',
    overview: {},
    records: [],
    alerts: [],
  },

  onLoad() {
    if (wx.getStorageSync('family_token')) {
      this.setData({ bound: true });
      this.fetchAll();
    }
  },

  onCode(e) {
    this.setData({ code: e.detail.value });
  },

  onBind() {
    const code = (this.data.code || '').trim();
    if (!code) return;
    wx.request({
      url: config.base_url + '/api/family/bind',
      method: 'POST',
      data: { invite_code: code },
      header: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + (wx.getStorageSync('token') || ''),
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          wx.setStorageSync('family_token', res.data.token);
          this.setData({ bound: true });
          this.fetchAll();
        } else {
          wx.showToast({ title: (res.data && res.data.detail) || '绑定失败', icon: 'none' });
        }
      },
      fail: () => wx.showToast({ title: '我这儿信号有点弱，咱们等会儿再说。', icon: 'none' }),
    });
  },

  fetchAll() {
    const header = { Authorization: 'Bearer ' + token() };
    wx.request({
      url: config.base_url + '/api/family/overview',
      header,
      success: (res) => {
        if (res.statusCode === 200) this.setData({ overview: res.data });
      },
    });
    wx.request({
      url: config.base_url + '/api/family/records',
      header,
      success: (res) => {
        if (res.statusCode !== 200) return;
        const records = (res.data.records || []).map((r) => ({
          game_type: GAME_TYPE_TEXT[r.game_type] || r.game_type,
          accuracy: r.total_count ? Math.round((r.correct_count / r.total_count) * 100) : 0,
          date: (r.created_at || '').slice(0, 10),
        }));
        this.setData({ records });
      },
    });
    wx.request({
      url: config.base_url + '/api/family/alerts',
      header,
      success: (res) => {
        if (res.statusCode === 200) this.setData({ alerts: res.data.alerts || [] });
      },
    });
  },
});
