/* ============================================================
 * i18n.js —— 界面文案字典（纯数据 + 取词函数，默认中文）
 *   MM_I18N.t(key, params)  按当前语言取词，{x} 占位符插值
 *   MM_I18N.lang            当前语言 'zh' | 'en'
 *   MM_I18N.set(lang)       切换语言（仅更新字典指针，DOM 刷新由交互层负责）
 * ============================================================ */
window.MM_I18N = (function () {
  'use strict';

  var STRINGS = {
    zh: {
      docTitle: 'Little P',
      brandName: '情绪工作台',
      navWall: '表情墙',
      navAlbum: '单图预览',
      langBtn: 'EN',
      themeToDark: '切换暗黑模式',
      themeToLight: '切换明亮模式',

      heroTitle: 'Little P', heroKicker: '桌面伙伴',
      backgroundHint: '移动鼠标，或点击空白处',
      heroSub: '小 P，你的桌面伙伴。',
      heroCta: '浏览表情',
      skipContent: '跳至表情', backToTop: '回到顶部',
      summonLabel: '召唤', summonBusy: '召唤中…',
      downloadPet: '下载 Windows 桌宠',
      summonOpeningApp: '正在召唤 Little P…',
      summonSuccess: '小 P 已来到网页 · 拖动顶部移动，点击互动',
      summonStartServer: '未检测到 Little P。请先下载安装并打开桌宠。',
      summonLocalPage: '请先下载安装并打开 Little P，然后重新点击召唤。',
      summonFailed: '召唤未完成，请稍后再试。',
      summonInvalidResponse: 'Little P 响应异常，请重新打开桌宠后重试。',
      studioNav: '表情工作台', meetNav: '小 P', workspaceTitle: 'Little P', webPetLabel: '网页小 P',
      sideNoteTitle: '一点情绪，一点陪伴。', sideNote: '开心、发呆或认真思考，小 P 都有自己的小表情。',
      realtime: '实时表情引擎', heroCaption: '两种造型，32 种表情。',
      heroTag: '今天，也要开心呀', heroTag2: '你好，新朋友',
      characterTitle: '选择小 P', characterCount: '种造型',
      expressionTitle: '表情', statesLabel: '种状态',
      stageInteract: '点击小 P 互动', footerCaption: '桌面伙伴 · 2.0',

      tabAll: '全部',
      galleryHint: '悬停感受动态，点击放大表情 · ← / → 切换',
      prevEmotion: '上一个表情',
      nextEmotion: '下一个表情',
      stageClose: '关闭预览',
      stageLabel: '表情主舞台',
      thumbSuffix: '缩略预览',
      castClick: '点击切换到该角色',

      industry_general: '通用',
      industry_learn: '仅供学习',
      industry_reference: '机器人',
      industry_classic: '冰蓝面屏',
      industry_ribbon: '粉色蝴蝶结',

      lblGroup: '分组',
      lblVariant: '造型',
      lblSketch: '线稿',
      lblTour: '自动播放',
      lblInterval: '间隔',


      toastTourOn: '自动播放已开启:「{name}」共 {n} 个表情',
      toastTourOff: '自动播放已关闭',
      toastSketchOn: '已切换为线稿模式(仅轮廓描边)',
      toastSketchOff: '已切回实体填充',
      toastCharacter: '已切换角色:{name}',
      toastVariant: '已切换形状:{name}',
      toastThemeDark: '已切换到暗黑模式',
      toastThemeLight: '已切换到明亮模式'
    },

    en: {
      docTitle: 'Little P',
      brandName: 'EMOTION STUDIO',
      navWall: 'Wall',
      navAlbum: 'Single view',
      langBtn: '中',
      themeToDark: 'Switch to dark mode',
      themeToLight: 'Switch to light mode',

      heroTitle: 'Little P', heroKicker: 'Desktop companion',
      backgroundHint: 'Move the pointer, or click the background',
      heroSub: 'Your desktop companion.',
      heroCta: 'Expressions',
      skipContent: 'Skip to expressions', backToTop: 'Back to top',
      summonLabel: 'Summon', summonBusy: 'Summoning…',
      downloadPet: 'Download for Windows',
      summonOpeningApp: 'Summoning Little P…',
      summonSuccess: 'Little P is on the page · drag the top bar to move, click to interact',
      summonStartServer: 'Little P was not detected. Install and open the desktop app first.',
      summonLocalPage: 'Install and open Little P, then click Summon again.',
      summonFailed: 'Could not summon Little P. Please try again.',
      summonInvalidResponse: 'Little P returned an invalid response. Reopen the app and try again.',
      studioNav: 'Emotion studio', meetNav: 'Little P', workspaceTitle: 'Little P', webPetLabel: 'Little P on the page',
      sideNoteTitle: 'Little feelings. Little moments.', sideNote: 'Happy, daydreaming or deep in thought. Little P has an expression for every moment.',
      realtime: 'Live expression engine', heroCaption: 'Two characters. 32 expressions.',
      heroTag: 'Find a little joy today', heroTag2: 'Hello, new friend',
      characterTitle: 'Choose yours', characterCount: 'characters',
      expressionTitle: 'Expressions', statesLabel: 'states',
      stageInteract: 'Click Little P to interact', footerCaption: 'Desktop companion · 2.0',

      tabAll: 'All',
      galleryHint: 'Hover to animate, click to explore · ← / → to switch',
      prevEmotion: 'Previous emotion',
      nextEmotion: 'Next emotion',
      stageClose: 'Close preview',
      stageLabel: 'Main emotion stage',
      thumbSuffix: 'thumbnail preview',
      castClick: 'click to switch to this character',

      industry_general: 'General',
      industry_learn: 'Learning only',
      industry_reference: 'Robot',
      industry_classic: 'Ice-blue screen',
      industry_ribbon: 'Pink ribbon',

      lblGroup: 'Group',
      lblVariant: 'Look',
      lblSketch: 'Sketch',
      lblTour: 'Autoplay',
      lblInterval: 'Interval',


      toastTourOn: 'Autoplay on: {n} emotions in "{name}"',
      toastTourOff: 'Autoplay off',
      toastSketchOn: 'Sketch mode on (outline only)',
      toastSketchOff: 'Back to solid fill',
      toastCharacter: 'Switched to {name}',
      toastVariant: 'Shape switched: {name}',
      toastThemeDark: 'Dark mode on',
      toastThemeLight: 'Light mode on'
    }
  };

  var api = {
    lang: 'zh',
    set: function (lang) {
      api.lang = STRINGS[lang] ? lang : 'zh';
      return api.lang;
    },
    t: function (key, params) {
      var s = (STRINGS[api.lang] && STRINGS[api.lang][key]) || STRINGS.zh[key] || key;
      if (params) {
        for (var k in params) s = s.split('{' + k + '}').join(String(params[k]));
      }
      return s;
    }
  };
  return api;
})();
