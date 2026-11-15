Component({
  data: {
    selected: 0,
    list: [
      { pagePath: '/pages/chat/chat', text: '说话' },
      { pagePath: '/pages/game/game', text: '练习' },
      { pagePath: '/pages/records/records', text: '记录' },
    ],
  },

  methods: {
    onTab(e) {
      const index = Number(e.currentTarget.dataset.index);
      const item = this.data.list[index];
      if (!item) return;
      const pages = getCurrentPages();
      const cur = pages[pages.length - 1];
      const route = item.pagePath.replace(/^\//, '');
      if (cur && cur.route === route) {
        if (typeof cur.onTabReselect === 'function') {
          cur.onTabReselect();
          return;
        }
        if (
          typeof cur.showGameMenu === 'function' &&
          cur.data.phase !== 'quiz' &&
          cur.data.phase !== 'remember'
        ) {
          cur.showGameMenu();
        }
        return;
      }
      this.setData({ selected: index });
      wx.switchTab({ url: item.pagePath });
    },
  },
});
