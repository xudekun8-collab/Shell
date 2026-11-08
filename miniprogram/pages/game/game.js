const { request } = require('../../utils/request.js');

const DIFFICULTY_TEXT = { 1: '今天轻松点', 2: '今天动动脑子', 3: '今天来点难的' };

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
    questions: [],
    word: '',
    options: [],
    result: null,
    main_text: '',
    sub_text: '',
    next_difficulty_text: '',
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
    await this.loadPrevCorrect();
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
      patch.questions = d.items.questions;
      patch.quiz_total = d.items.questions.length;
      patch.quiz_index = 0;
      patch.word = d.items.questions[0].word;
      patch.options = d.items.questions[0].options;
    }
    this.setData(patch);
    if (d.game_type === 'memory_box') {
      this.scheduleRemember();
    } else {
      this.scheduleQuiz();
    }
  },

  async loadPrevCorrect() {
    const res = await request({ url: '/api/records/' + this.data.user_id + '?limit=50' });
    if (res.ok && res.data && res.data.records) {
      const prev = res.data.records.find((r) => r.game_type === this.data.game_type);
      this._prevCorrect = prev ? prev.correct_count : null;
    } else {
      this._prevCorrect = null;
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
      if (this.data.game_type === 'memory_box') {
        this.setData({ quiz_index: next, quiz_target: this.data.quizzes[next].target });
      } else {
        this.setData({
          quiz_index: next,
          word: this.data.questions[next].word,
          options: this.data.questions[next].options,
        });
      }
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
    const idx = this.data.quiz_index;
    const value = e.currentTarget.dataset.value;
    this.setData({ answers: this.data.answers.concat([{ index: idx, value: value }]) });
    this.nextQuiz();
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
    const correct = res.data.correct;
    let mainText = '';
    let subText = '';
    if (correct === 0) {
      mainText = this.data.game_type === 'memory_box'
        ? '今天有点累，咱们下回少记几样，慢慢来。'
        : '今天这些不太熟，下回我挑更好认的给您。';
    } else {
      const verb = this.data.game_type === 'memory_box' ? '记住了' : '分对了';
      const shortVerb = this.data.game_type === 'memory_box' ? '记了' : '分对了';
      mainText = '今天' + verb + ' ' + correct + ' 样东西';
      if (this._prevCorrect === null || this._prevCorrect === undefined) {
        subText = '头一回就' + shortVerb + ' ' + correct + ' 样，挺好';
      } else if (correct > this._prevCorrect) {
        subText = '比上次多' + shortVerb + ' ' + (correct - this._prevCorrect) + ' 样，真不错';
      }
    }
    this.setData({
      result: res.data,
      main_text: mainText,
      sub_text: subText,
      next_difficulty_text: DIFFICULTY_TEXT[res.data.next_difficulty] || DIFFICULTY_TEXT[2],
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
