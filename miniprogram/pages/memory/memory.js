const { request, clearElderSession } = require('../../utils/request.js');
const { getUserId } = require('../../utils/user.js');
const {
  SPEAK_SPEEDS,
  DEFAULT_SPEAK_SPEED,
  normalizeSpeakSpeed,
} = require('../../utils/constants.js');

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
    loaded: false,
    autoSendVoice: true,
    autoSpeak: true,
    speakSpeed: DEFAULT_SPEAK_SPEED,
    speakSpeeds: SPEAK_SPEEDS,
    editProfileOpen: false,
    nicknameInput: '',
    interestsInput: '',
    taboosInput: '',
    profileSaving: false,
  },

  onLoad() {
    this.setData({ user_id: getUserId() });
  },

  onShow() {
    this._loadVoiceSettings();
    this.fetch();
  },

  onPullDownRefresh() {
    this.fetch().then(() => wx.stopPullDownRefresh());
  },

  _loadVoiceSettings() {
    this.setData({
      autoSendVoice: wx.getStorageSync('auto_send_voice') !== false,
      autoSpeak: wx.getStorageSync('auto_speak') !== false,
      speakSpeed: normalizeSpeakSpeed(wx.getStorageSync('speak_speed')),
    });
  },

  toggleAutoSend() {
    const autoSendVoice = !this.data.autoSendVoice;
    wx.setStorageSync('auto_send_voice', autoSendVoice);
    this.setData({ autoSendVoice });
  },

  toggleAutoSpeak() {
    const autoSpeak = !this.data.autoSpeak;
    wx.setStorageSync('auto_speak', autoSpeak);
    this.setData({ autoSpeak });
  },

  setSpeakSpeed(e) {
    const speakSpeed = Number(e.currentTarget.dataset.speed);
    if (!SPEAK_SPEEDS.some((item) => item.value === speakSpeed)) return;
    wx.setStorageSync('speak_speed', speakSpeed);
    this.setData({ speakSpeed: speakSpeed });
  },

  clearConversation() {
    wx.showModal({
      title: '提示',
      content: '确定要清空这段对话吗',
      confirmText: '清空',
      cancelText: '再想想',
      success: (result) => {
        if (!result.confirm) return;
        // 换 thread_id 是唯一可靠的信号：本页可能是从「说话」页进来的，
        // 也可能是从「记录」页进来的，后一种拿不到聊天页实例，
        // 由聊天页 onShow 里的 _syncThread 按 storage 对齐，两条入口结果一致。
        const oldThreadId = wx.getStorageSync('thread_id');
        if (oldThreadId) {
          wx.removeStorageSync('chat_history_' + oldThreadId);
        }
        const threadId = 'wx_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
        wx.setStorageSync('thread_id', threadId);
        const chatPage = getCurrentPages().find((page) => page.route === 'pages/chat/chat');
        if (chatPage) {
          if (typeof chatPage._clearPendingTimers === 'function') chatPage._clearPendingTimers();
          if (typeof chatPage._stopAudio === 'function') chatPage._stopAudio();
          chatPage.setData({
            messages: [],
            ended: false,
            input: '',
            pendingText: '',
            pendingCountdown: 0,
            thread_id: threadId,
          });
        }
        wx.showToast({ title: '已经清空', icon: 'success' });
      },
    });
  },

  logout() {
    wx.showModal({
      title: '提示',
      content: '确定要退出登录吗',
      confirmText: '退出',
      cancelText: '再想想',
      success: (result) => {
        if (!result.confirm) return;
        clearElderSession();
        wx.reLaunch({ url: '/pages/login/login' });
      },
    });
  },

  async fetch() {
    if (this._fetching) return;
    this._fetching = true;
    if (!this.data.loaded) this.setData({ loading: true, load_error: false });
    try {
      const res = await request({ url: '/api/memories' });
      if (res.ok && res.data) {
        const profile = res.data.profile || null;
        if (profile) {
          const interests = profile.interests || [];
          const taboos = profile.taboos || [];
          // 标签化展示比「喜欢：下棋、早上散步」更好扫读，也便于以后单个删改
          profile.interest_tags = interests;
          profile.taboo_tags = taboos;
          profile.has_prefs = interests.length > 0 || taboos.length > 0;
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
          .map((s, index) => ({ key: 'session-' + index, content: (s.content || '').trim() }))
          .filter((s) => s.content);
        this.setData({
          profile: profile,
          sessions: sessions,
          loading: false,
          load_error: false,
          loaded: true,
          nicknameInput: profile ? profile.nickname : '',
          interestsInput: profile ? (profile.interests || []).join('、') : '',
          taboosInput: profile ? (profile.taboos || []).join('、') : '',
        });
        this._applyEvents(events);
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

  toggleProfileEdit() {
    if (this.data.profileSaving) return;
    const profile = this.data.profile;
    this.setData({
      editProfileOpen: !this.data.editProfileOpen,
      nicknameInput: profile ? profile.nickname : '',
      interestsInput: profile ? (profile.interests || []).join('、') : '',
      taboosInput: profile ? (profile.taboos || []).join('、') : '',
    });
  },

  onNicknameInput(e) {
    this.setData({ nicknameInput: e.detail.value });
  },

  onInterestsInput(e) {
    this.setData({ interestsInput: e.detail.value });
  },

  onTaboosInput(e) {
    this.setData({ taboosInput: e.detail.value });
  },

  _splitTags(text) {
    return (text || '')
      .split(/[、,，]/)
      .map((item) => item.trim())
      .filter((item) => item);
  },

  async saveProfile() {
    const nickname = (this.data.nicknameInput || '').trim();
    if (!nickname || this.data.profileSaving) {
      if (!nickname) wx.showToast({ title: '请写怎么称呼您', icon: 'none' });
      return;
    }
    this.setData({ profileSaving: true });
    const res = await request({
      url: '/api/profile',
      method: 'PUT',
      data: {
        nickname,
        interests: this._splitTags(this.data.interestsInput),
        taboos: this._splitTags(this.data.taboosInput),
      },
    });
    if (res.ok) {
      this.setData({ editProfileOpen: false, profileSaving: false });
      await this.fetch();
      wx.showToast({ title: '改好了', icon: 'success' });
    } else {
      this.setData({ profileSaving: false });
      wx.showToast({ title: res.msg || '没保存上，再试一次', icon: 'none' });
    }
  },

  async onInvite() {
    const res = await request({ url: '/api/family/invite', method: 'POST' });
    if (res.ok && res.data && res.data.invite_code) {
      wx.showModal({
        title: '邀请码',
        content: '请把这串邀请码告诉家人：' + res.data.invite_code + '（24 小时内有效）',
        showCancel: false,
      });
    } else {
      wx.showToast({ title: '生成失败，再试一次', icon: 'none' });
    }
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
