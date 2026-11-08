const { request } = require('../../utils/request.js');
const { DEMO_MODE } = require('../../utils/constants.js');

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
    if (DEMO_MODE) {
      await this._demoLogin();
    } else {
      await this._wxLogin();
    }
  },

  async _demoLogin() {
    const res = await request({
      url: '/api/auth/demo',
      method: 'POST',
      data: { user_id: 'demo_user_1' },
      skipAuthRedirect: true,
    });
    if (res.ok) {
      this._saveAndEnter(res.data);
    } else {
      wx.showToast({ title: '演示登录没开，请确认后端', icon: 'none' });
    }
  },

  async _wxLogin() {
    const code = await this._getWxCode();
    if (!code) {
      wx.showToast({ title: '没拿到微信凭证，再试一次', icon: 'none' });
      return;
    }
    const res = await request({
      url: '/api/auth/wx',
      method: 'POST',
      data: { code },
      skipAuthRedirect: true,
    });
    if (res.ok) {
      this._saveAndEnter(res.data);
    } else {
      wx.showToast({ title: '登录没成功，再试一次', icon: 'none' });
    }
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
