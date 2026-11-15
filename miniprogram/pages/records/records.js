const { request } = require('../../utils/request.js');
const { GAME_TYPE_TEXT, DIFFICULTY_TEXT } = require('../../utils/constants.js');
const { getUserId } = require('../../utils/user.js');
const { formatDuration, dateLabel, listKey } = require('../../utils/format.js');

const CACHE_KEY = 'records_cache_v1';

function mapRecords(data) {
  const records = (data.records || data.list || []).map((r, index) => ({
    key: listKey(r, index),
    game_type: r.game_type,
    game_type_text: GAME_TYPE_TEXT[r.game_type] || r.game_type,
    difficulty: r.difficulty,
    difficulty_text: DIFFICULTY_TEXT[r.difficulty] || '多动动脑',
    total_count: r.total_count || 0,
    duration: r.duration_sec,
    duration_text: formatDuration(r.duration_sec),
    abandoned: r.abandoned,
    date: (r.created_at || '').slice(0, 10),
    date_label: dateLabel((r.created_at || '').slice(0, 10)),
  }));
  const rawSummary = data.summary || {};
  const byType = (rawSummary.by_type || [])
    .map((b) => ({
      game_type_text: GAME_TYPE_TEXT[b.game_type] || b.game_type,
      total: b.total,
    }))
    .filter((b) => b.total > 0);
  const totalDuration = rawSummary.total_duration || 0;
  const summary = {
    total: rawSummary.total || 0,
    total_duration: totalDuration,
    total_duration_text: formatDuration(totalDuration),
    by_type: byType,
    streak_days: rawSummary.streak_days || 0,
  };
  return { records, summary };
}

Page({
  data: {
    user_id: '',
    records: [],
    summary: {
      total: 0,
      total_duration: 0,
      total_duration_text: '0 秒',
      by_type: [],
      streak_days: 0,
    },
    loaded: false,
    loading: false,
    load_error: false,
  },

  onLoad() {
    this.setData({ user_id: getUserId() });
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 2 });
    }
    // 先渲染上次的缓存，再静默刷新，避免每次切回来都闪一下「正在读…」
    this._renderCache();
    this.fetch();
  },

  onPullDownRefresh() {
    this.fetch().then(() => wx.stopPullDownRefresh());
  },

  _renderCache() {
    if (this.data.loaded) return;
    const cached = wx.getStorageSync(CACHE_KEY);
    if (!cached || !cached.records) return;
    // 老缓存没有 key，「今天/昨天」也要按当前日期重算
    const records = cached.records.map((item, index) =>
      Object.assign({}, item, {
        key: item.key || listKey({ created_at: item.date, game_type: item.game_type }, index),
        date_label: dateLabel(item.date),
      })
    );
    this.setData({
      records: records,
      summary: cached.summary,
      loaded: true,
      loading: false,
    });
  },

  async fetch() {
    if (this._fetching) return;
    this._fetching = true;
    if (!this.data.loaded) this.setData({ loading: true, load_error: false });
    try {
      const res = await request({ url: '/api/records?limit=20' });
      if (res.ok && res.data) {
        const mapped = mapRecords(res.data);
        this.setData({
          records: mapped.records,
          summary: mapped.summary,
          loaded: true,
          loading: false,
          load_error: false,
        });
        try {
          wx.setStorageSync(CACHE_KEY, mapped);
        } catch (err) {
          console.warn('缓存训练记录失败：', err);
        }
      } else {
        this.setData({ loading: false, load_error: !this.data.loaded });
      }
    } finally {
      this._fetching = false;
    }
  },

  retry() {
    this.fetch();
  },

  goGame() {
    wx.switchTab({ url: '/pages/game/game' });
  },

  goSettings() {
    wx.navigateTo({ url: '/pages/memory/memory' });
  },
});
