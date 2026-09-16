(function () {
  var images = [
    { src: "assets/bing/bing-20260915.jpg", caption: "斯瓦尔巴群岛玩耍的北极熊幼崽，挪威" },
    { src: "assets/bing/bing-20260914.jpg", caption: "红绿金刚鹦鹉" },
    { src: "assets/bing/bing-20260913.jpg", caption: "地肤田，中国" },
    { src: "assets/bing/bing-20260912.jpg", caption: "米苏里纳群峰，多洛米蒂山脉，威尼托大区，意大利" },
    { src: "assets/bing/bing-20260911.jpg", caption: "墨西哥近海围猎沙丁鱼饵球的加州海狮，太平洋" },
    { src: "assets/bing/bing-20260910.jpg", caption: "滨海自由城，法国里维埃拉，法国" },
    { src: "assets/bing/bing-20260909.jpg", caption: "奥尔韦拉航拍图，安达卢西亚，西班牙" },
    { src: "assets/bing/bing-20260908.jpg", caption: "安科拉附近的加比特凯尼海滩，卡纳塔克邦，印度" }
  ];

  var lastUrl = null;

  function setHeroBackground() {
    var hero = document.querySelector(".home-hero");
    if (!hero) return;
    if (location.href === lastUrl) return;
    lastUrl = location.href;

    var pick = images[Math.floor(Math.random() * images.length)];
    hero.style.backgroundImage = "url('" + pick.src + "')";

    var credit = hero.querySelector(".home-hero__credit");
    if (credit) {
      credit.textContent = pick.caption;
    }
  }

  function run() {
    try {
      setHeroBackground();
    } catch (e) {
      /* 忽略，保证页面其他功能不受影响 */
    }
  }

  if (typeof document$ !== "undefined" && document$.subscribe) {
    try {
      document$.subscribe(run);
    } catch (e) {
      /* 忽略 */
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
