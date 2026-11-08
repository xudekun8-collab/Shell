const { request } = require('../../utils/request.js');

Page({
  data: {
    user_id: 'demo_user_1',
    records: [],
    summary: { total: 0, avg_accuracy: 0, total_duration: 0 },
    loaded: false,
  },

  onShow() {
    this.fetch();
  },

  async fetch() {
    const res = await request({ url: '/api/records/' + this.data.user_id + '?limit=20' });
    if (res.ok && res.data) {
      const list = (res.data.records || res.data.list || []).map((r) => ({
        game_type: r.game_type,
        difficulty: r.difficulty,
        accuracy: r.total_count ? Math.round((r.correct_count / r.total_count) * 100) : 0,
        duration: r.duration_sec,
        date: (r.created_at || '').slice(0, 10),
      }));
      const summary = res.data.summary || {
        total: list.length,
        avg_accuracy: list.length ? Math.round(list.reduce((s, x) => s + x.accuracy, 0) / list.length) : 0,
        total_duration: list.reduce((s, x) => s + x.duration, 0),
      };
      this.setData({ records: list, summary: summary, loaded: true });
    } else {
      this.setData({ records: [], summary: { total: 0, avg_accuracy: 0, total_duration: 0 }, loaded: true });
    }
  },
});
