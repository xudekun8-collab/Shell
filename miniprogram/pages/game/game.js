const { request } = require('../../utils/request.js');
const { DIFFICULTY_TEXT } = require('../../utils/constants.js');
const { getUserId } = require('../../utils/user.js');
const LEVEL_TEXT = { 1: '轻松', 2: '动脑', 3: '挑战' };

Page({
  data: {
    user_id: '',
    game_type: 'memory_box',
    session_id: '',
    difficulty: 0,
    time_limit_sec: 10,
    level_text: '轻松',
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
    selectedValue: '',
    answering: false,
    countdown: 0,
    timeoutTip: false,
    error_kind: '',
    result: null,
    main_text: '',
    sub_text: '',
    result_note: '',
    next_difficulty_text: '',
  },

  onLoad(query) {
    this.setData({
      user_id: getUserId(),
      game_type: (query && query.game_type) || 'memory_box',
    });
    this.startGame();
  },

  onHide() {
    this._remainingSec = this.data.countdown;
    this.clearAllTimers();
  },

  onShow() {
    if (this.data.phase === 'quiz') {
      this.startCountdown(this._remainingSec);
    } else if (this.data.phase === 'remember') {
      this.scheduleRemember();
    }
  },

  onUnload() {
    this.clearAllTimers();
  },

  clearTimer() {
    if (this._timer) {
      clearTimeout(this._timer);
      this._timer = null;
    }
  },

  clearCountdown() {
    if (this._countdownTimer) {
      clearInterval(this._countdownTimer);
      this._countdownTimer = null;
    }
  },

  clearTimeoutTimer() {
    if (this._timeoutTimer) {
      clearTimeout(this._timeoutTimer);
      this._timeoutTimer = null;
    }
  },

  clearAnswerTimer() {
    if (this._answerTimer) {
      clearTimeout(this._answerTimer);
      this._answerTimer = null;
    }
  },

  clearAllTimers() {
    this.clearTimer();
    this.clearCountdown();
    this.clearTimeoutTimer();
    this.clearAnswerTimer();
  },

  async startGame() {
    this.clearAllTimers();
    this._startTime = Date.now();
    this.setData({
      phase: 'loading',
      answers: [],
      result: null,
      selectedValue: '',
      answering: false,
      timeoutTip: false,
      error_kind: '',
    });
    await this.loadPrevCorrect();
    const res = await request({
      url: '/api/game/start',
      method: 'POST',
      data: { user_id: this.data.user_id, game_type: this.data.game_type },
    });
    if (!res.ok) {
      this.setData({ phase: 'error', error_kind: 'network' });
      return;
    }
    const d = res.data;
    const patch = {
      session_id: d.session_id,
      difficulty: d.difficulty,
      time_limit_sec: d.time_limit_sec,
      level_text: LEVEL_TEXT[d.difficulty] || '轻松',
      quiz_index: 0,
      quiz_total: 0,
      selectedValue: '',
      answering: false,
      timeoutTip: false,
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
      this.startCountdown();
    }
  },

  async loadPrevCorrect() {
    const res = await request({ url: '/api/records/' + this.data.user_id + '?limit=5' });
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
        this.setData({
          phase: 'quiz',
          quiz_index: 0,
          quiz_target: this.data.quizzes[0].target,
          selectedValue: '',
          answering: false,
          timeoutTip: false,
        });
        this.startCountdown();
      }
    }, 2000);
  },

  startCountdown(initialSec) {
    this.clearCountdown();
    this.clearTimeoutTimer();
    const start = initialSec != null && initialSec > 0 ? initialSec : this.data.time_limit_sec;
    this.setData({ countdown: start, timeoutTip: false, answering: false, selectedValue: '' });
    this._countdownTimer = setInterval(() => {
      const next = this.data.countdown - 1;
      if (next <= 0) {
        this.clearCountdown();
        this.setData({ countdown: 0, timeoutTip: true });
        this._timeoutTimer = setTimeout(() => this.nextQuiz(), 1000);
      } else {
        this.setData({ countdown: next });
      }
    }, 1000);
  },

  nextQuiz() {
    this.clearTimer();
    this.clearCountdown();
    this.clearTimeoutTimer();
    this.clearAnswerTimer();
    const next = this.data.quiz_index + 1;
    if (next < this.data.quiz_total) {
      this.setData({ quiz_index: next, selectedValue: '', answering: false, timeoutTip: false });
      if (this.data.game_type === 'memory_box') {
        this.setData({ quiz_target: this.data.quizzes[next].target });
      } else {
        this.setData({
          word: this.data.questions[next].word,
          options: this.data.questions[next].options,
        });
      }
      this.startCountdown();
    } else {
      this.submit(false);
    }
  },

  answerMemory(e) {
    if (this.data.answering || this.data.timeoutTip) return;
    this.clearAllTimers();
    const raw = e.currentTarget.dataset.value;
    const value = raw === '1';
    const idx = this.data.quiz_index;
    this.setData({
      selectedValue: raw,
      answering: true,
      answers: this.data.answers.concat([{ index: idx, value }]),
    });
    this._answerTimer = setTimeout(() => {
      this.setData({ selectedValue: '', answering: false });
      this.nextQuiz();
    }, 350);
  },

  answerCategory(e) {
    if (this.data.answering || this.data.timeoutTip) return;
    this.clearAllTimers();
    const value = e.currentTarget.dataset.value;
    const idx = this.data.quiz_index;
    this.setData({
      selectedValue: value,
      answering: true,
      answers: this.data.answers.concat([{ index: idx, value }]),
    });
    this._answerTimer = setTimeout(() => {
      this.setData({ selectedValue: '', answering: false });
      this.nextQuiz();
    }, 350);
  },

  tooHard() {
    wx.showModal({
      title: '提示',
      content: '这次先不玩了，确定吗',
      confirmText: '不玩了',
      cancelText: '继续玩',
      success: (r) => {
        if (r.confirm) {
          this.clearAllTimers();
          this.submit(true);
        }
      },
    });
  },

  async submit(abandoned) {
    this.clearAllTimers();
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
      const kind = res.status === 404 ? 'expired' : 'network';
      this.setData({ phase: 'error', error_kind: kind });
      return;
    }
    const d = res.data;
    const lines = (d.summary_text || '').split('\n');
    const mainText = (lines[0] || '').trim();
    const noteText = (lines[1] || '').trim();
    const correct = d.correct;
    let subText = '';
    if (correct === 0) {
      subText = this.data.game_type === 'memory_box'
        ? '今天有点累，咱们下回少记几样，慢慢来。'
        : '今天这些不太熟，下回我挑更好认的给您。';
    } else if (correct > 0) {
      if (this._prevCorrect === null || this._prevCorrect === undefined) {
        subText = this.data.game_type === 'memory_box'
          ? '头一回就记 ' + correct + ' 样，挺好'
          : '头一回就对 ' + correct + ' 题，挺好';
      } else if (correct > this._prevCorrect) {
        const diff = correct - this._prevCorrect;
        subText = this.data.game_type === 'memory_box'
          ? '比上次多记了 ' + diff + ' 样，真不错'
          : '比上次多对了 ' + diff + ' 题，真不错';
      }
    }
    this.setData({
      result: d,
      main_text: mainText,
      sub_text: subText,
      result_note: noteText,
      next_difficulty_text: DIFFICULTY_TEXT[d.next_difficulty] || DIFFICULTY_TEXT[2],
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
