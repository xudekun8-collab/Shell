const GAME_TYPE_TEXT = { memory_box: '记东西', category_sort: '分分类' };
const DIFFICULTY_TEXT = { 1: '轻松一点', 2: '多动动脑', 3: '来点难的' };
const PHRASE_GROUPS = [
  { title: '身上', items: ['我昨晚没睡好', '今天身上不太舒服', '我吃过了', '该吃药了'] },
  { title: '家里人', items: ['我孙女快来看我了', '我想我儿子了', '今天孙子给我打电话了', '我老伴以前爱唱戏'] },
  { title: '日常', items: ['今天天气不错', '我下楼走了一圈', '咱们聊会儿', '陪我玩个游戏'] },
];
const QUICK_PHRASES = ['我吃过了', '今天身上不太舒服', '咱们聊会儿', '陪我玩个游戏'];

module.exports = { GAME_TYPE_TEXT, DIFFICULTY_TEXT, PHRASE_GROUPS, QUICK_PHRASES };
