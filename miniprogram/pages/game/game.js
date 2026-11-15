const { request } = require('../../utils/request.js');
const { DIFFICULTY_TEXT, GAME_TYPE_TEXT } = require('../../utils/constants.js');
const { getUserId } = require('../../utils/user.js');
const MEMORY_GAME_TYPES = ['memory_box', 'number_seq'];
const PRACTICE_NOTICE = '这些是陪伴练习，不是认知筛查，也不能代替医院评估。';
const GAME_INTROS = {
  memory_box: {
    text: '会一样一样给您看，您看清楚后点“看好了，下一个”，全部看完再开始答题。',
    example: '比如先看到“钥匙、雨伞”，再判断“雨伞”刚才有没有出现。',
  },
  category_sort: {
    text: '看一个词，从选项里选出它属于哪一类。不确定也没关系，按自己的判断选。',
    example: '比如看到“苹果”，可以选择“水果”。',
  },
  number_seq: {
    text: '先看几秒数字，数字消失后找出刚才那一串。每局可以重新看一次。',
    example: '比如先记住一串数字，三到五位都有可能，等一下再从同样长度的选项里找出来。',
  },
  common_sense: {
    text: '读一个生活场景，选出更稳妥的做法。这不是考试，按平时经验选就好。',
    example: '比如冬天路面结冰时，选择“慢一点”。',
  },
};
const MENU_GAMES = [
  { game_type: 'memory_box', mark: '记', title: GAME_TYPE_TEXT.memory_box, desc: '练习刚才看过内容的识别' },
  { game_type: 'category_sort', mark: '分', title: GAME_TYPE_TEXT.category_sort, desc: '练习物品和概念的归类' },
  { game_type: 'number_seq', mark: '数', title: GAME_TYPE_TEXT.number_seq, desc: '练习短时记住数字顺序' },
  { game_type: 'common_sense', mark: '常', title: GAME_TYPE_TEXT.common_sense, desc: '练习日常情境判断' },
];

function isMemoryStyle(gameType) {
  return MEMORY_GAME_TYPES.indexOf(gameType) >= 0;
}

function stringOptions(values) {
  return (values || []).map((value) => ({ label: value, value: value }));
}

Page({
  data: {
    user_id: '',
    game_type: 'memory_box',
    session_id: '',
    difficulty: 0,
    // 智能体建议的档位，只在下一局生效一次，见 startGame
    hint_difficulty: 0,
    time_limit_sec: 10,
    level_text: '轻松',
    phase: 'loading',
    intro_title: '',
    intro_text: '',
    intro_example: '',
    practice_notice: PRACTICE_NOTICE,
    practice_mode: 'relaxed',
    timed_mode: false,
    menuGames: MENU_GAMES,
    is_memory_style: false,
    is_sequence: false,
    uses_item_unit: false,
    show_items: [],
    remember_index: 0,
    remember_total: 0,
    remember_text: '',
    remember_label: '请记住这几样',
    quizzes: [],
    sequence_questions: [],
    quiz_index: 0,
    quiz_total: 0,
    quiz_question: '',
    answers: [],
    questions: [],
    options: [],
    quiz_is_boolean: false,
    replay_used: false,
    selectedValue: '',
    answering: false,
    skippedIndexes: [],
    skipStreak: 0,
    feedback: { index: -1, result: '' },
    feedback_text: '',
    countdown: 0,
    timeoutTip: false,
    error_kind: '',
    result: null,
    main_text: '',
    sub_text: '',
    result_note: '',
    next_difficulty_text: '',
    wrong_details: [],
    streak_text: '今天第一次练',
  },

  onLoad(query) {
    const gameType = query && query.game_type;
    if (gameType) {
      this.showIntro(gameType);
    } else {
      this.setData({ user_id: getUserId(), phase: 'menu' });
      this.loadStreak();
    }
  },

  onHide() {
    this._keepScreen(false);
    if (this._startTime) {
      this._elapsedMs = (this._elapsedMs || 0) + Math.max(0, Date.now() - this._startTime);
      this._startTime = 0;
    }
    this._remainingSec = this.data.countdown;
    this.clearAllTimers();
  },

  // 记东西/记数字有 3 秒观察期，屏幕自动变暗会让老人看不见题目
  _keepScreen(on) {
    if (typeof wx.setKeepScreenOn !== 'function') return;
    try {
      wx.setKeepScreenOn({ keepScreenOn: !!on });
    } catch (err) {}
  },

  onShow() {
    this._startTime = Date.now();
    this._keepScreen(true);
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 1 });
    }
    if (getApp().globalData.showGameMenu) {
      getApp().globalData.showGameMenu = false;
      this.clearAllTimers();
      this.setData({ phase: 'menu' });
      this.loadStreak();
      return;
    }
    const pending = getApp().globalData.pendingGame;
    if (pending) {
      getApp().globalData.pendingGame = null;
      this.showIntro(pending.game_type || 'memory_box', pending.difficulty || 0);
      return;
    }
    if (this.data.phase === 'menu') {
      this.loadStreak();
      return;
    }
    if (this.data.phase === 'quiz') {
      if (this.data.feedback.index >= 0) {
        this.nextQuiz();
        return;
      }
      if (this.data.timeoutTip) {
        this.nextQuiz();
        return;
      }
      this.startCountdown(this._remainingSec);
    } else if (this.data.phase === 'remember') {
      this.scheduleRemember();
    }
  },

  onUnload() {
    this._keepScreen(false);
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
    this._elapsedMs = 0;
    this._lastRememberTap = 0;
    this.setData({
      phase: 'loading',
      answers: [],
      result: null,
      selectedValue: '',
      answering: false,
      timeoutTip: false,
      error_kind: '',
      skippedIndexes: [],
      skipStreak: 0,
      feedback: { index: -1, result: '' },
      feedback_text: '',
    });
    await this.loadPrevCorrect();
    // 智能体在 start_game 里给的档位只作一次性提示：发出去就清掉，
    // 否则下一局会一直沿用旧档位，自适应难度失效
    const hint = this.data.hint_difficulty;
    const payload = { game_type: this.data.game_type };
    if (hint >= 1 && hint <= 3) payload.difficulty = hint;
    this.setData({ hint_difficulty: 0 });
    const res = await request({
      url: '/api/game/start',
      method: 'POST',
      data: payload,
    });
    if (this.data.phase !== 'loading') return;
    if (!res.ok) {
      this.setData({ phase: 'error', error_kind: 'network' });
      return;
    }
    const d = res.data;
    const patch = {
      session_id: d.session_id,
      difficulty: d.difficulty,
      time_limit_sec: d.time_limit_sec,
      level_text: DIFFICULTY_TEXT[d.difficulty] || DIFFICULTY_TEXT[2],
      quiz_index: 0,
      quiz_total: 0,
      selectedValue: '',
      answering: false,
      timeoutTip: false,
      replay_used: false,
      wrong_details: [],
      feedback: { index: -1, result: '' },
      feedback_text: '',
      uses_item_unit: !!d.items.show_items,
      quiz_is_boolean: false,
    };
    if (isMemoryStyle(d.game_type)) {
      patch.phase = 'remember';
      patch.is_memory_style = true;
      patch.remember_index = 0;
      if (d.items.show_items) {
        patch.is_sequence = false;
        patch.show_items = d.items.show_items;
        patch.remember_total = d.items.show_items.length;
        patch.remember_text = d.items.show_items[0];
        patch.remember_label = '请看清这一样';
        patch.quizzes = d.items.quizzes;
        patch.quiz_total = d.items.quizzes.length;
      } else {
        patch.is_sequence = true;
        patch.sequence_questions = d.items.questions;
        patch.remember_total = d.items.questions.length;
        patch.remember_text = d.items.questions[0].digits;
        patch.remember_label = '请记住这串数字';
        patch.quiz_total = d.items.questions.length;
      }
    } else {
      patch.phase = 'quiz';
      patch.is_memory_style = false;
      patch.is_sequence = false;
      patch.questions = d.items.questions;
      patch.quiz_total = d.items.questions.length;
      patch.quiz_index = 0;
      patch.quiz_question = d.items.questions[0].word
        ? '「' + d.items.questions[0].word + '」属于哪一类'
        : d.items.questions[0].question;
      patch.options = stringOptions(d.items.questions[0].options);
    }
    this.setData(patch);
    if (isMemoryStyle(d.game_type)) {
      this.scheduleRemember();
    } else {
      this.startCountdown();
    }
  },

  chooseGame(e) {
    const gameType = e.currentTarget.dataset.gameType;
    this.showIntro(gameType);
  },

  showIntro(gameType, difficulty) {
    const intro = GAME_INTROS[gameType] || GAME_INTROS.memory_box;
    this.setData({
      user_id: getUserId(),
      game_type: gameType,
      difficulty: 0,
      hint_difficulty: difficulty || 0,
      intro_title: GAME_TYPE_TEXT[gameType] || gameType,
      intro_text: intro.text,
      intro_example: intro.example,
      phase: 'intro',
    });
  },

  setPracticeMode(e) {
    const mode = e.currentTarget.dataset.mode;
    this.setData({
      practice_mode: mode,
      timed_mode: mode === 'timed',
    });
  },

  startFromIntro() {
    this.setData({ phase: 'loading' });
    this.startGame();
  },

  showGameMenu() {
    this.clearAllTimers();
    this.setData({ phase: 'menu' });
    this.loadStreak();
  },

  async loadStreak() {
    if (this._streakLoading) return;
    this._streakLoading = true;
    try {
      const res = await request({ url: '/api/records?limit=1' });
      if (!res.ok || !res.data || !res.data.summary) return;
      const days = Number(res.data.summary.streak_days) || 0;
      this.setData({
        streak_text: days > 1 ? '已经练了 ' + days + ' 天' : '今天第一次练',
      });
    } finally {
      this._streakLoading = false;
    }
  },

  showQuestion(index) {
    if (this.data.is_sequence) {
      const question = this.data.sequence_questions[index];
      this.setData({
        quiz_question: '刚才的数字是哪一个',
        options: stringOptions(question.options),
        quiz_is_boolean: false,
      });
    } else if (this.data.is_memory_style) {
      this.setData({
        quiz_question: '刚才有「' + this.data.quizzes[index].target + '」吗',
        options: [
          { label: '有', value: '1' },
          { label: '没有', value: '0' },
        ],
        quiz_is_boolean: true,
      });
    } else {
      const question = this.data.questions[index];
      this.setData({
        quiz_question: question.word
          ? '「' + question.word + '」属于哪一类'
          : question.question,
        options: stringOptions(question.options),
        quiz_is_boolean: false,
      });
    }
  },

  async loadPrevCorrect() {
    const res = await request({ url: '/api/records?limit=10' });
    if (res.ok && res.data && res.data.records) {
      const sameType = res.data.records.filter((r) => r.game_type === this.data.game_type);
      const prev = sameType.find((r) => r.abandoned !== 1);
      this._prevCorrect = prev ? prev.correct_count : null;
      this._prevDifficulty = prev ? prev.difficulty : null;
      this._hadIncomplete = !prev && sameType.length > 0;
    } else {
      this._prevCorrect = null;
      this._prevDifficulty = null;
      this._hadIncomplete = false;
    }
  },

  scheduleRemember() {
    this.clearTimer();
    this.clearCountdown();
    if (this.data.is_sequence) {
      const question = this.data.sequence_questions[this.data.remember_index];
      this.setData({ remember_text: question.digits });
      this._timer = setTimeout(() => {
        this.setData({
          phase: 'quiz',
          quiz_index: this.data.remember_index,
          selectedValue: '',
          answering: false,
          timeoutTip: false,
        });
        this.showQuestion(this.data.remember_index);
        this.startCountdown();
      }, question.show_ms || 3000);
      return;
    }
    this.setData({ remember_text: this.data.show_items[this.data.remember_index] });
  },

  nextRememberItem() {
    if (this.data.phase !== 'remember' || this.data.is_sequence) return;
    const now = Date.now();
    if (this._lastRememberTap && now - this._lastRememberTap < 400) return;
    this._lastRememberTap = now;
    this.clearTimer();
    const next = this.data.remember_index + 1;
    if (next < this.data.remember_total) {
      this.setData({ remember_index: next, remember_text: this.data.show_items[next] });
      return;
    }
    this.setData({
      phase: 'quiz',
      quiz_index: 0,
      selectedValue: '',
      answering: false,
      timeoutTip: false,
    });
    this.showQuestion(0);
    this.startCountdown();
  },

  startCountdown(initialSec) {
    this.clearCountdown();
    this.clearTimeoutTimer();
    if (!this.data.timed_mode) {
      this.setData({ countdown: 0, timeoutTip: false, answering: false, selectedValue: '' });
      return;
    }
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
      this.setData({
        quiz_index: next,
        selectedValue: '',
        answering: false,
        timeoutTip: false,
        feedback: { index: -1, result: '' },
        feedback_text: '',
      });
      if (this.data.is_sequence) {
        this.setData({
          phase: 'remember',
          remember_index: next,
          remember_text: this.data.sequence_questions[next].digits,
        });
        this.scheduleRemember();
      } else {
        this.showQuestion(next);
        this.startCountdown();
      }
    } else {
      this.submit(false);
    }
  },

  answer(e) {
    if (this.data.answering || this.data.timeoutTip) return;
    this.clearAllTimers();
    const raw = e.currentTarget.dataset.value;
    const value = this.data.quiz_is_boolean ? raw === '1' : raw;
    const idx = this.data.quiz_index;
    const option = this.data.options.find((item) => item.value === raw);
    const label = option ? option.label : String(raw);
    let result = 'neutral';
    let correctLabel = '';
    if (this.data.is_sequence) {
      correctLabel = this.data.sequence_questions[idx].digits;
      result = label === correctLabel ? 'right' : 'wrong';
    } else if (this.data.is_memory_style) {
      correctLabel = this.data.quizzes[idx].appeared ? '有' : '没有';
      result = label === correctLabel ? 'right' : 'wrong';
    }
    const options = this.data.options.map((item) => {
      let feedbackClass = '';
      let feedbackText = '';
      if (result !== 'neutral') {
        feedbackClass = 'muted';
        if (item.label === correctLabel) {
          feedbackClass = 'correct';
          feedbackText = '对';
        } else if (result === 'wrong' && item.value === raw) {
          feedbackClass = 'wrong';
          feedbackText = '您选的';
        }
      }
      return { ...item, feedbackClass, feedbackText };
    });
    let wrongFeedback = '这题是「' + correctLabel + '」';
    if (this.data.is_memory_style && !this.data.is_sequence) {
      const target = this.data.quizzes[idx].target;
      wrongFeedback = this.data.quizzes[idx].appeared
        ? '刚才有「' + target + '」'
        : '刚才没有「' + target + '」';
    }
    const feedbackText =
      result === 'right' ? '对了' : result === 'wrong' ? wrongFeedback : '记下了';
    this.setData({
      selectedValue: raw,
      answering: true,
      answers: this.data.answers
        .filter((answer) => answer.index !== idx)
        .concat([{ index: idx, value, label }]),
      skipStreak: 0,
      feedback: { index: idx, result },
      feedback_text: feedbackText,
      options,
    });
    this._answerTimer = setTimeout(() => {
      this.setData({
        selectedValue: '',
        answering: false,
        feedback: { index: -1, result: '' },
        feedback_text: '',
      });
      this.nextQuiz();
    }, 1200);
  },

  skipQuestion() {
    if (this.data.answering || this.data.timeoutTip) return;
    this.clearAllTimers();
    const skippedIndexes = this.data.skippedIndexes.concat([this.data.quiz_index]);
    const skipStreak = this.data.skipStreak + 1;
    this.setData({
      skippedIndexes,
      skipStreak,
      selectedValue: '',
      answering: true,
      feedback: { index: -1, result: '' },
      feedback_text: '',
    });
    if (skipStreak < 3) {
      this.nextQuiz();
      return;
    }
    wx.showModal({
      title: '提示',
      content: '今天先练到这儿？',
      confirmText: '结束',
      cancelText: '继续',
      success: (res) => {
        if (res.confirm) {
          this.submit(true);
        } else {
          this.setData({ skipStreak: 0, answering: false });
          this.nextQuiz();
        }
      },
      fail: () => {
        this.setData({ skipStreak: 0, answering: false });
        this.nextQuiz();
      },
    });
  },

  replaySequence() {
    if (
      this.data.answering ||
      this.data.timeoutTip ||
      !this.data.is_sequence ||
      this.data.replay_used ||
      this.data.phase !== 'quiz'
    ) {
      return;
    }
    this.clearAllTimers();
    this.setData({
      replay_used: true,
      phase: 'remember',
      remember_index: this.data.quiz_index,
      selectedValue: '',
      answering: false,
      timeoutTip: false,
    });
    this.scheduleRemember();
  },

  tooHard() {
    wx.showModal({
      title: '提示',
      content: '结束这局吗？',
      confirmText: '结束',
      cancelText: '继续',
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
    const segmentMs = this._startTime ? Math.max(0, Date.now() - this._startTime) : 0;
    const elapsedMs = (this._elapsedMs || 0) + segmentMs;
    this._startTime = 0;
    this._elapsedMs = elapsedMs;
    const res = await request({
      url: '/api/game/submit',
      method: 'POST',
      data: {
        session_id: this.data.session_id,
        answers: this.data.answers.map((item) => ({ index: item.index, value: item.value })),
        duration_sec: Math.floor(elapsedMs / 1000),
        abandoned: abandoned,
      },
    });
    if (!res.ok) {
      const kind = res.status === 404 ? 'expired' : 'network';
      this.setData({ phase: 'error', error_kind: kind });
      return;
    }
    const d = res.data;
    if (d.total === 0) {
      this.setData({ phase: 'menu' });
      this.loadStreak();
      return;
    }
    const lines = (d.summary_text || '').split('\n');
    let mainText = (lines[0] || '').trim();
    const noteText = (lines[1] || '').trim();
    const correct = d.correct;
    const answerByIndex = {};
    this.data.answers.forEach((item) => {
      answerByIndex[item.index] = item;
    });
    if (!this.data.timed_mode) {
      mainText = mainText.replace(/[，,]?\s*用时\s*\d+\s*秒(?=。|$)/, '');
    }
    let subText = '';
    const unit = this.data.uses_item_unit ? '样' : '题';
    if (correct === 0) {
      subText = this.data.uses_item_unit
        ? '今天有点累，咱们下回少记几样，慢慢来。'
        : '今天这些不太熟，下回我挑更好认的给您。';
    } else if (correct > 0) {
      if (this._prevCorrect === null || this._prevCorrect === undefined) {
        subText = this._hadIncomplete
          ? '上次没做完，这次先记个数'
          : '头一回就' + (unit === '样' ? '记 ' : '对 ') + correct + ' ' + unit + '，挺好';
      } else if (this._prevDifficulty !== d.difficulty) {
        subText = '这次 ' + d.total + ' 题对了 ' + correct + ' 题，换了个难度，慢慢来';
      } else if (correct > this._prevCorrect) {
        const diff = correct - this._prevCorrect;
        subText = '比上次多' + (unit === '样' ? '记了 ' : '对了 ') + diff + ' ' + unit + '，真不错';
      }
    }
    this.setData({
      result: d,
      main_text: mainText,
      sub_text: subText,
      result_note: noteText,
      next_difficulty_text: this.data.timed_mode
        ? DIFFICULTY_TEXT[d.next_difficulty] || DIFFICULTY_TEXT[2]
        : '换几道新的给您',
      wrong_details: (d.details || [])
        .filter((item) => !item.correct)
        .map((item) => {
          const answer = answerByIndex[item.index];
          let answerText = '这题没答';
          if (this.data.skippedIndexes.indexOf(item.index) >= 0) {
            answerText = '这题跳过了';
          } else if (answer) {
            answerText = '您选的是：' + answer.label;
          }
          return { ...item, answer_text: answerText };
        }),
      phase: 'result',
    });
  },

  retry() {
    this.startGame();
  },

  backToChat() {
    wx.switchTab({ url: '/pages/chat/chat' });
  },
});
