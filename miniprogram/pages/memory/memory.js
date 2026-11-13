const { request } = require('../../utils/request.js');
const { getUserId } = require('../../utils/user.js');

const TOP_EVENT_LIMIT = 5;
const DETAIL_EVENT_LIMIT = 20;

function parseDate(dateStr) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(dateStr || '');
  if (!m) return null;
  const year = parseInt(m[1], 10);
  const month = parseInt(m[2], 10);
  const day = parseInt(m[3], 10);
  return {
    label: month + '月' + day + '日',
    monthSort: year * 100 + month,
    monthLabel: year + '年' + month + '月',
  };
}

function groupEventsByMonth(events) {
  const map = {};
  const keys = [];
  events.forEach((e) => {
    const key = e.month_sort;
    if (!map[key]) {
      map[key] = { month_label: e.month_label, items: [] };
      keys.push(key);
    }
    map[key].items.push(e);
  });
  keys.sort((a, b) => {
    if (a === -1 && b === -1) return 0;
    if (a === -1) return 1;
    if (b === -1) return -1;
    return b - a;
  });
  const groups = keys.map((k) => map[k]);
  groups.forEach((g) => {
    g.items.sort((a, b) => (a.occurred_at < b.occurred_at ? 1 : -1));
  });
  return groups;
}

function sliceGroups(groups, limit) {
  const out = [];
  let count = 0;
  for (const g of groups) {
    if (count >= limit) break;
    const take = Math.min(g.items.length, limit - count);
    out.push({ month_label: g.month_label, items: g.items.slice(0, take) });
    count += take;
  }
  return out;
}

Page({
  data: {
    user_id: '',
    profile: null,
    events: [],
    eventsShown: [],
    eventsRemainder: 0,
    eventsExpanded: false,
    eventGroups: [],
    eventGroupsShown: [],
    detailRemainder: 0,
    detailExpanded: false,
    sessions: [],
    showDetail: false,
    loading: false,
    load_error: false,
  },

  onLoad() {
    this.setData({ user_id: getUserId() });
  },

  onShow() {
    this.fetch();
  },

  async fetch() {
    this.setData({ loading: true, load_error: false });
    const res = await request({ url: '/api/memories' });
    if (res.ok && res.data) {
      const profile = res.data.profile || null;
      if (profile) {
        profile.interests_text = (profile.interests || []).length
          ? (profile.interests || []).join('、')
          : '还没告诉我';
        profile.taboos_text = (profile.taboos || []).length
          ? (profile.taboos || []).join('、')
          : '还没告诉我';
      }
      const events = (res.data.events || []).map((e) => {
        const dt = parseDate(e.occurred_at);
        return {
          memory_id: e.memory_id,
          // 仅展示层把"我"改成"您"，不写回库、不参与判分
          content: (e.content || '').replace(/我(?!们)/g, '您'),
          occurred_at: (e.occurred_at || '').slice(0, 10),
          date_text: dt ? dt.label : '日期不详',
          month_sort: dt ? dt.monthSort : -1,
          month_label: dt ? dt.monthLabel : '日期不详',
        };
      });
      const sessions = (res.data.sessions || [])
        .map((s) => ({ content: (s.content || '').trim() }))
        .filter((s) => s.content);
      this.setData({ profile: profile, sessions: sessions, loading: false, load_error: false });
      this._applyEvents(events);
    } else {
      this.setData({ loading: false, load_error: true });
    }
  },

  retry() {
    this.fetch();
  },

  async onInvite() {
    const res = await request({ url: '/api/family/invite', method: 'POST' });
    if (res.ok && res.data && res.data.invite_code) {
      wx.showModal({
        title: '邀请码',
        content: '请把这 6 位邀请码告诉家人：' + res.data.invite_code + '（24 小时内有效）',
        showCancel: false,
      });
    } else {
      wx.showToast({ title: '生成失败，再试一次', icon: 'none' });
    }
  },

  goFamily() {
    wx.navigateTo({ url: '/pages/family/family' });
  },

  _applyEvents(events) {
    const eventGroups = groupEventsByMonth(events);
    this.setData({
      events: events,
      eventsShown: events.slice(0, TOP_EVENT_LIMIT),
      eventsRemainder: Math.max(0, events.length - TOP_EVENT_LIMIT),
      eventsExpanded: false,
      eventGroups: eventGroups,
      eventGroupsShown: sliceGroups(eventGroups, DETAIL_EVENT_LIMIT),
      detailRemainder: Math.max(0, events.length - DETAIL_EVENT_LIMIT),
      detailExpanded: false,
    });
  },

  toggleDetail() {
    this.setData({ showDetail: !this.data.showDetail });
  },

  toggleEvents() {
    if (this.data.eventsExpanded) {
      this.setData({ eventsShown: this.data.events.slice(0, TOP_EVENT_LIMIT), eventsExpanded: false });
    } else {
      this.setData({ eventsShown: this.data.events, eventsExpanded: true });
    }
  },

  toggleDetailEvents() {
    if (this.data.detailExpanded) {
      this.setData({
        eventGroupsShown: sliceGroups(this.data.eventGroups, DETAIL_EVENT_LIMIT),
        detailExpanded: false,
      });
    } else {
      this.setData({ eventGroupsShown: this.data.eventGroups, detailExpanded: true });
    }
  },

  onDelete(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '提示',
      content: '这条我就忘掉啦，确定吗？',
      confirmText: '删除',
      cancelText: '再想想',
      success: async (r) => {
        if (!r.confirm) return;
        const index = this.data.events.findIndex((x) => x.memory_id === id);
        if (index < 0) return;
        const removed = this.data.events[index];
        this._applyEvents(this.data.events.filter((x) => x.memory_id !== id));
        const res = await request({
          url: '/api/memories/' + id,
          method: 'DELETE',
        });
        if (res.ok) {
          this.fetch();
        } else {
          const restored = this.data.events.slice();
          restored.splice(Math.min(index, restored.length), 0, removed);
          this._applyEvents(restored);
          wx.showToast({ title: '没删掉，再试一次', icon: 'none' });
        }
      },
    });
  },
});
