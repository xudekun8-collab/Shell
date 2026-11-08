const { request } = require('../../utils/request.js');

Page({
  data: {
    showContent: false,
  },

  onLoad() {
    if (wx.getStorageSync('token')) {
      wx.switchTab({ url: '/pages/chat/chat' });
    } else {
      this.setData({ showContent: true });
    }
  },

  async onStart() {
    const demoOk = await this._demoLogin();
    if (demoOk) return;
    const wxOk = await this._wxLogin();
    if (!wxOk) {
      wx.showToast({ title: '没连上，再试一次', icon: 'none' });
    }
  },

  async _demoLogin() {
    const res = await request({
      url: '/api/auth/demo',
      method: 'POST',
      data: { user_id: 'demo_user_1' },
      timeout: 400,
      skipAuthRedirect: true,
    });
    if (res.ok) {
      this._saveAndEnter(res.data);
      return true;
    }
    return false;
  },

  async _wxLogin() {
    const code = await this._getWxCode();
    if (!code) {
      return false;
    }
    const res = await request({
      url: '/api/auth/wx',
      method: 'POST',
      data: { code },
      skipAuthRedirect: true,
    });
    if (res.ok) {
      this._saveAndEnter(res.data);
      return true;
    }
    return false;
  },

  _getWxCode() {
    return new Promise((resolve) => {
      wx.login({
        success: (r) => resolve(r.code || ''),
        fail: () => resolve(''),
      });
    });
  },

  _saveAndEnter(data) {
    wx.setStorageSync('token', data.token);
    wx.setStorageSync('user_id', data.user_id);
    wx.switchTab({ url: '/pages/chat/chat' });
  },
});
