const { request } = require('../../utils/request.js');

Page({
  data: {
    user_id: 'demo_user_1',
    game_type: 'memory_box',
    session_id: '',
    difficulty: 0,
    time_limit_sec: 10,
    phase: 'loading',
    show_items: [],
    remember_index: 0,
    remember_total: 0,
    remember_text: '',
    quizzes: [],
    quiz_index: 0,
    quiz_total: 0,
    quiz_target: '',
    answers: [],
    word: '',
    options: [],
    result: null,
    summaryLines: [],
    diff_text: '',
  },

  onLoad(query) {
    this.setData({
      user_id: wx.getStorageSync('user_id') || 'demo_user_1',
      game_type: (query && query.game_type) || 'memory_box',
    });
    this.startGame();
  },

  onUnload() {
    this.clearTimer();
  },

  clearTimer() {
    if (this._timer) {
      clearTimeout(this._timer);
      this._timer = null;
    }
  },

  async startGame() {
    this.clearTimer();
    this._startTime = Date.now();
    this.setData({ phase: 'loading', answers: [], result: null });
    const res = await request({
      url: '/api/game/start',
      method: 'POST',
      data: { user_id: this.data.user_id, game_type: this.data.game_type },
    });
    if (!res.ok) {
      this.setData({ phase: 'error' });
      return;
    }
    const d = res.data;
    const patch = {
      session_id: d.session_id,
      difficulty: d.difficulty,
      time_limit_sec: d.time_limit_sec,
      quiz_index: 0,
      quiz_total: 0,
    };
    if (d.game_type === 'memory_box') {
      patch.phase = 'remember';
      patch.show_items = d.items.show_items;
      patch.remember_total = d.items.show_items.length;
      patch.remember_index = 0;
      patch.remember_text = d.items.show_items[0];
      patch.quizzes = d.items.quizzes;
      patch.quiz_total = d.items.quizzes.length;
      patch.quiz_target = d.items.quizzes[0].target;
    } else {
      patch.phase = 'quiz';
      patch.word = d.items.word;
      patch.options = d.items.options;
      patch.quiz_total = 1;
    }
    this.setData(patch);
    if (d.game_type === 'memory_box') {
      this.scheduleRemember();
    } else {
      this.scheduleQuiz();
    }
  },

  scheduleRemember() {
    this.clearTimer();
    this._timer = setTimeout(() => {
      const next = this.data.remember_index + 1;
      if (next < this.data.remember_total) {
        this.setData({ remember_index: next, remember_text: this.data.show_items[next] });
        this.scheduleRemember();
      } else {
        this.setData({ phase: 'quiz', quiz_index: 0, quiz_target: this.data.quizzes[0].target });
        this.scheduleQuiz();
      }
    }, 2000);
  },

  scheduleQuiz() {
    this.clearTimer();
    this._timer = setTimeout(() => {
      this.nextQuiz();
    }, this.data.time_limit_sec * 1000);
  },

  nextQuiz() {
    this.clearTimer();
    const next = this.data.quiz_index + 1;
    if (next < this.data.quiz_total) {
      this.setData({ quiz_index: next, quiz_target: this.data.quizzes[next].target });
      this.scheduleQuiz();
    } else {
      this.submit(false);
    }
  },

  answerMemory(e) {
    this.clearTimer();
    const value = e.currentTarget.dataset.value === '1';
    const idx = this.data.quiz_index;
    this.setData({ answers: this.data.answers.concat([{ index: idx, value: value }]) });
    this.nextQuiz();
  },

  answerCategory(e) {
    this.clearTimer();
    this.setData({ answers: [{ index: 0, value: e.currentTarget.dataset.value }] });
    this.submit(false);
  },

  tooHard() {
    wx.showModal({
      title: '提示',
      content: '这次先不玩了，确定吗',
      confirmText: '不玩了',
      cancelText: '继续玩',
      success: (r) => {
        if (r.confirm) {
          this.clearTimer();
          this.submit(true);
        }
      },
    });
  },

  async submit(abandoned) {
    this.clearTimer();
    const res = await request({
      url: '/api/game/submit',
      method: 'POST',
      data: {
        session_id: this.data.session_id,
        answers: this.data.answers,
        duration_sec: this._startTime ? Math.floor((Date.now() - this._startTime) / 1000) : 0,
        abandoned: abandoned,
      },
    });
    if (!res.ok) {
      this.setData({ phase: 'error' });
      return;
    }
    const cur = this.data.difficulty;
    const nxt = res.data.next_difficulty;
    let diffText = '难度不变';
    if (nxt > cur) diffText = '下一局难度会提高';
    else if (nxt < cur) diffText = '下一局难度会降低';
    this.setData({
      result: res.data,
      summaryLines: (res.data.summary_text || '').split('\n'),
      diff_text: diffText,
      phase: 'result',
    });
  },

  retry() {
    this.startGame();
  },

  backToChat() {
    wx.navigateBack({
      fail: () => wx.redirectTo({ url: '/pages/chat/chat' }),
    });
  },
});
