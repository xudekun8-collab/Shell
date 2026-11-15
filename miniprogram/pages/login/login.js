const { request, clearElderSession } = require('../../utils/request.js');
const { envVersion, baseUrl, setApiBase } = require('../../utils/config.js');

Page({
  data: {
    showContent: false,
    connecting: false,
  },

  onLoad() {
    if (wx.getStorageSync('token')) {
      wx.switchTab({ url: '/pages/chat/chat' });
    } else {
      this.setData({ showContent: true });
    }
  },

  async onStart() {
    if (this.data.connecting) return;
    this.setData({ connecting: true });
    try {
      // 正式版一律走 wx.login，演示后门只在开发版 / 体验版保留：
      // 否则线上任何人点一下都会进同一个 demo 账号。
      if (envVersion() === 'release') {
        const wxOk = await this._wxLogin();
        if (!wxOk) wx.showToast({ title: '没连上，再试一次', icon: 'none' });
        return;
      }
      const demoOk = await this._demoLogin();
      if (demoOk) return;
      const wxOk = await this._wxLogin();
      if (!wxOk) {
        wx.showToast({ title: '没连上，再试一次', icon: 'none' });
      }
    } finally {
      this.setData({ connecting: false });
    }
  },

  goFamilyEntry() {
    wx.navigateTo({ url: '/pages/family/family' });
  },

  // 真机联调换网络时不必改代码重新编译：长按图标临时覆盖接口地址。
  // 正式版不开放，避免误导用户。地址只存在本地 storage。
  onLongPressMark() {
    if (envVersion() === 'release') return;
    wx.showModal({
      title: '接口地址',
      content: '现在是 ' + baseUrl() + '。留空恢复默认。',
      editable: true,
      placeholderText: '例如 http://192.168.0.105:8000',
      success: (res) => {
        if (!res.confirm) return;
        const saved = setApiBase(res.content);
        wx.showToast({
          title: saved ? '记下了，重新进入生效' : '已恢复默认地址',
          icon: 'none',
        });
      },
    });
  },

  async _demoLogin() {
    const res = await request({
      url: '/api/auth/demo',
      method: 'POST',
      data: { user_id: 'demo_user_1' },
      // 后端冷启动 + 建表可能要一两秒，超时给太短会把演示登录误判成失败
      timeout: 2500,
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
    clearElderSession();
    wx.setStorageSync('token', data.token);
    wx.setStorageSync('user_id', data.user_id);
    wx.switchTab({ url: '/pages/chat/chat' });
  },
});
