const { request } = require('../../utils/request.js');
const { GAME_TYPE_TEXT, DIFFICULTY_TEXT } = require('../../utils/constants.js');
const { getUserId } = require('../../utils/user.js');
const { formatDuration, dateLabel, listKey, dayKey, groupByDay } = require('../../utils/format.js');

// v1 的缓存里没有 correct_count，字段形状变了，换键避免读到旧数据
const CACHE_KEY = 'records_cache_v2';

// 题型色块上的字：比图标省事，老人也认得出
const TYPE_MARK = {
  memory_box: '记',
  category_sort: '分',
  number_seq: '数',
  common_sense: '常',
};

// 结果用「量」不用「率」：老人端不出现百分比，正确为零时也不写 0，避免挫败
function resultOf(item) {
  if (item.abandoned === 1) return { text: '没做完', tone: 'muted' };
  if (!item.total_count) return { text: '只开了个头', tone: 'muted' };
  if (!item.correct_count) return { text: '这局练完了', tone: 'muted' };
  return { text: '对了 ' + item.correct_count + ' 题', tone: 'good' };
}

function mapRecords(data) {
  const today = dayKey();
  let todayCount = 0;
  let todayDuration = 0;

  const records = (data.records || data.list || []).map((r, index) => {
    const duration = r.duration_sec || 0;
    const date = (r.created_at || '').slice(0, 10);
    const result = resultOf(r);
    if (date === today) {
      todayCount += 1;
      todayDuration += duration;
    }
    return {
      key: listKey(r, index),
      game_type: r.game_type,
      game_type_text: GAME_TYPE_TEXT[r.game_type] || r.game_type,
      type_mark: TYPE_MARK[r.game_type] || '练',
      difficulty_text: DIFFICULTY_TEXT[r.difficulty] || '多动动脑',
      total_count: r.total_count || 0,
      correct_count: r.correct_count || 0,
      duration: duration,
      duration_text: formatDuration(duration),
      abandoned: r.abandoned,
      result_text: result.text,
      result_tone: result.tone,
      date: date,
      date_label: dateLabel(date),
    };
  });

  const rawSummary = data.summary || {};
  const byType = (rawSummary.by_type || [])
    .map((b) => ({
      game_type_text: GAME_TYPE_TEXT[b.game_type] || b.game_type,
      total: b.total,
    }))
    .filter((b) => b.total > 0);
  const totalDuration = rawSummary.total_duration || 0;

  return {
    records: records,
    groups: groupByDay(records),
    summary: {
      total: rawSummary.total || 0,
      total_duration: totalDuration,
      total_duration_text: formatDuration(totalDuration),
      by_type: byType,
      streak_days: rawSummary.streak_days || 0,
      today_count: todayCount,
      today_duration: todayDuration,
      today_duration_text: formatDuration(todayDuration),
    },
  };
}

// 列表已按时间倒序，groupByDay 会把同一天的归到一组（实现放在 utils/format.js，便于单测）
Page({
  data: {
    user_id: '',
    groups: [],
    summary: {
      total: 0,
      total_duration: 0,
      total_duration_text: '0 秒',
      by_type: [],
      streak_days: 0,
      today_count: 0,
      today_duration: 0,
      today_duration_text: '0 秒',
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
    const records = cached.records.map((item, index) =>
      Object.assign({}, item, {
        key: item.key || listKey({ created_at: item.date, game_type: item.game_type }, index),
        date_label: dateLabel(item.date),
      })
    );
    // 缓存可能是昨天写的，「今天练了几次」要按当前日期重算
    const today = dayKey();
    let todayCount = 0;
    let todayDuration = 0;
    records.forEach((item) => {
      if (item.date === today) {
        todayCount += 1;
        todayDuration += item.duration || 0;
      }
    });
    const summary = Object.assign({}, cached.summary, {
      today_count: todayCount,
      today_duration: todayDuration,
      today_duration_text: formatDuration(todayDuration),
    });
    this.setData({
      groups: groupByDay(records),
      summary: summary,
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
          groups: mapped.groups,
          summary: mapped.summary,
          loaded: true,
          loading: false,
          load_error: false,
        });
        try {
          wx.setStorageSync(CACHE_KEY, { records: mapped.records, summary: mapped.summary });
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
