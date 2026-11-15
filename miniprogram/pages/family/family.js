const { request } = require('../../utils/request.js');
const { GAME_TYPE_TEXT } = require('../../utils/constants.js');

function familyToken() {
  return wx.getStorageSync('family_token') || '';
}

Page({
  data: {
    bound: false,
    code: '',
    overview: {},
    records: [],
    alerts: [],
    noteText: '',
    noteSending: false,
    interestText: '',
    interestSaving: false,
    binding: false,
    loading: false,
    load_error: false,
  },

  onLoad() {
    if (familyToken()) {
      this.setData({ bound: true });
      this.fetchAll();
    }
  },

  onPullDownRefresh() {
    if (!this.data.bound) {
      wx.stopPullDownRefresh();
      return;
    }
    this.fetchAll().then(() => wx.stopPullDownRefresh());
  },

  _authOptions(extra) {
    return Object.assign(
      {
        authToken: familyToken(),
        onUnauthorized: () => this._expireFamilySession(),
      },
      extra
    );
  },

  onCode(e) {
    this.setData({ code: e.detail.value });
  },

  onNoteInput(e) {
    this.setData({ noteText: e.detail.value });
  },

  onInterestInput(e) {
    this.setData({ interestText: e.detail.value });
  },

  _expireFamilySession() {
    if (!this.data.bound) return;
    wx.removeStorageSync('family_token');
    this.setData({
      bound: false,
      code: '',
      overview: {},
      records: [],
      alerts: [],
      noteText: '',
      noteSending: false,
      interestText: '',
      interestSaving: false,
      loading: false,
      load_error: false,
    });
    wx.showToast({ title: '登录失效，请重新绑定', icon: 'none' });
  },

  async onSendNote() {
    const text = (this.data.noteText || '').trim();
    if (!text || this.data.noteSending) return;
    this.setData({ noteSending: true });
    const res = await request(
      this._authOptions({
        url: '/api/family/note',
        method: 'POST',
        data: { text },
      })
    );
    this.setData({ noteSending: false });
    if (!this.data.bound) return;
    if (res.ok) {
      this.setData({ noteText: '' });
      wx.showToast({ title: '留好了', icon: 'success' });
    } else {
      wx.showToast({ title: res.detail || res.msg || '没留上，再试一次', icon: 'none' });
    }
  },

  async onAddInterest() {
    const text = (this.data.interestText || '').trim();
    if (!text || this.data.interestSaving) return;
    this.setData({ interestSaving: true });
    const res = await request(
      this._authOptions({
        url: '/api/family/interest',
        method: 'POST',
        data: { text },
      })
    );
    this.setData({ interestSaving: false });
    if (!this.data.bound) return;
    if (res.ok) {
      this.setData({ interestText: '' });
      wx.showToast({ title: '记下了', icon: 'success' });
    } else {
      wx.showToast({ title: res.detail || res.msg || '没记上，再试一次', icon: 'none' });
    }
  },

  async onBind() {
    const code = (this.data.code || '').trim();
    if (!code || this.data.binding) return;
    this.setData({ binding: true });
    const res = await request({
      url: '/api/family/bind',
      method: 'POST',
      data: { invite_code: code },
      authToken: '',
      onUnauthorized: () => {},
    });
    this.setData({ binding: false });
    if (res.ok && res.data && res.data.token) {
      wx.setStorageSync('family_token', res.data.token);
      this.setData({ bound: true, load_error: false });
      this.fetchAll();
      return;
    }
    wx.showToast({ title: res.detail || res.msg || '绑定失败', icon: 'none' });
  },

  onExit() {
    wx.removeStorageSync('family_token');
    this.setData({
      bound: false,
      code: '',
      overview: {},
      records: [],
      alerts: [],
      noteText: '',
      noteSending: false,
      interestText: '',
      interestSaving: false,
      loading: false,
      load_error: false,
    });
  },

  async fetchAll() {
    if (this._fetching || !this.data.bound) return;
    this._fetching = true;
    this.setData({ loading: true, load_error: false });
    try {
      const [overviewRes, recordsRes, alertsRes] = await Promise.all([
        request(this._authOptions({ url: '/api/family/overview' })),
        request(this._authOptions({ url: '/api/family/records' })),
        request(this._authOptions({ url: '/api/family/alerts' })),
      ]);
      // 401 已触发退出绑定，不再回写数据
      if (!this.data.bound) return;
      if (!overviewRes.ok || !recordsRes.ok || !alertsRes.ok) {
        this.setData({ loading: false, load_error: true });
        return;
      }
      const records = ((recordsRes.data && recordsRes.data.records) || []).map((r, index) => ({
        key: 'rec-' + ((r.created_at || '') + '|' + (r.game_type || '') + '|' + index),
        game_type: GAME_TYPE_TEXT[r.game_type] || r.game_type,
        accuracy: r.total_count ? Math.round((r.correct_count / r.total_count) * 100) : 0,
        abandoned: r.abandoned,
        date: (r.created_at || '').slice(0, 10),
      }));
      const alerts = ((alertsRes.data && alertsRes.data.alerts) || []).map((a, index) => ({
        key: 'alert-' + ((a.type || '') + '|' + (a.created_at || '') + '|' + index),
        detail: a.detail,
        created_at: a.created_at,
      }));
      this.setData({
        overview: overviewRes.data || {},
        records: records,
        alerts: alerts,
        loading: false,
        load_error: false,
      });
    } finally {
      this._fetching = false;
    }
  },

  retry() {
    this.fetchAll();
  },
});
