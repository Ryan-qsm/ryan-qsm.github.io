(function () {
  var baseUrl = "";
  if (document.currentScript && document.currentScript.src) {
    baseUrl = document.currentScript.src.replace(/javascripts\/hero-bg\.js.*$/, "");
  }

  function applyBackground(images) {
    var hero = document.querySelector(".home-hero");
    if (!hero) return;

    var pick = images[Math.floor(Math.random() * images.length)];
    hero.style.backgroundImage = "url('" + baseUrl + pick.src + "')";

    var credit = hero.querySelector(".home-hero__credit");
    if (credit) {
      credit.textContent = pick.caption || "";
    }
  }

  function setHeroBackground() {
    var hero = document.querySelector(".home-hero");
    if (!hero || hero.dataset.bgReady === "1") return;
    hero.dataset.bgReady = "1";

    fetch(baseUrl + "assets/bing/manifest.json?t=" + Date.now())
      .then(function (response) {
        if (!response.ok) throw new Error("manifest 加载失败");
        return response.json();
      })
      .then(function (images) {
        if (images && images.length) {
          applyBackground(images);
        }
      })
      .catch(function () {
        /* 读取失败时保持纯色背景，不影响页面其他功能 */
      });
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
