const { request } = require('../../utils/request.js');

const DIFFICULTY_TEXT = { 1: '轻松一点', 2: '多动动脑', 3: '来点难的' };
const GAME_TYPE_TEXT = { memory_box: '记东西', category_sort: '分分类' };

function formatDuration(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds || 0));
  if (s < 60) return s + ' 秒';
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m + ' 分 ' + r + ' 秒';
}

Page({
  data: {
    user_id: 'demo_user_1',
    records: [],
    summary: {
      total: 0,
      avg_accuracy: 0,
      total_duration: 0,
      total_duration_text: '0 秒',
      by_type: [],
    },
    loaded: false,
    loading: false,
    load_error: false,
  },

  onShow() {
    this.fetch();
  },

  async fetch() {
    this.setData({ loading: true, load_error: false });
    const res = await request({ url: '/api/records/' + this.data.user_id + '?limit=20' });
    if (res.ok && res.data) {
      const list = (res.data.records || res.data.list || []).map((r) => ({
        game_type: r.game_type,
        game_type_text: GAME_TYPE_TEXT[r.game_type] || r.game_type,
        difficulty: r.difficulty,
        difficulty_text: DIFFICULTY_TEXT[r.difficulty] || '多动动脑',
        accuracy: r.total_count ? Math.round((r.correct_count / r.total_count) * 100) : 0,
        duration: r.duration_sec,
        date: (r.created_at || '').slice(0, 10),
      }));
      const rawSummary = res.data.summary || {};
      const byType = (rawSummary.by_type || [])
        .map((b) => ({
          game_type_text: GAME_TYPE_TEXT[b.game_type] || b.game_type,
          total: b.total,
          avg_accuracy: b.avg_accuracy,
        }))
        .filter((b) => b.total > 0);
      const totalDuration = rawSummary.total_duration || 0;
      this.setData({
        records: list,
        summary: {
          total: rawSummary.total || 0,
          avg_accuracy: rawSummary.avg_accuracy || 0,
          total_duration: totalDuration,
          total_duration_text: formatDuration(totalDuration),
          by_type: byType,
        },
        loaded: true,
        loading: false,
        load_error: false,
      });
    } else {
      this.setData({ loading: false, load_error: true });
    }
  },

  retry() {
    this.fetch();
  },
});
