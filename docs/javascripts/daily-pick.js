(function () {
  var baseUrl = "";
  if (document.currentScript && document.currentScript.src) {
    baseUrl = document.currentScript.src.replace(/javascripts\/daily-pick\.js.*$/, "");
  }

  var cache = {};

  function dayIndex() {
    /* 北京时间每天 09:00 切换：把时间轴前移 9 小时再取天数 */
    var ms = Date.now() + 8 * 3600 * 1000 - 9 * 3600 * 1000;
    return Math.floor(ms / 86400000);
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text) node.textContent = text;
    return node;
  }

  function render(box, data) {
    var items = data && data.items;
    if (!items || !items.length) throw new Error("数据为空");

    var item = items[dayIndex() % items.length];

    var coverWrap = el("div", "daily-pick__cover-wrap");
    var img = el("img", "daily-pick__cover");
    img.alt = item.title;
    img.loading = "lazy";
    img.referrerPolicy = "no-referrer-when-downgrade";
    img.src = item.image;
    img.addEventListener("error", function () {
      coverWrap.classList.add("daily-pick__cover-wrap--empty");
      if (img.parentNode) img.parentNode.removeChild(img);
    });
    coverWrap.appendChild(img);

    var body = el("div", "daily-pick__body");

    var titleRow = el("h2", "daily-pick__title");
    titleRow.appendChild(document.createTextNode(item.title));
    if (item.rating) {
      titleRow.appendChild(el("span", "daily-pick__score", "豆瓣 " + item.rating));
    }
    body.appendChild(titleRow);

    if (item.meta) {
      body.appendChild(el("p", "daily-pick__meta", item.meta));
    }

    if (item.quote) {
      var quote = el("blockquote", "daily-pick__quote");
      quote.appendChild(document.createTextNode(item.quote));
      var fromText = item.quote_from ? "—— " + item.quote_from : "";
      if (item.quote_stars) {
        var stars = "";
        for (var i = 0; i < item.quote_stars; i++) stars += "★";
        fromText += (fromText ? " · " : "") + stars;
      }
      if (fromText) quote.appendChild(el("span", "daily-pick__from", fromText));
      body.appendChild(quote);
    }

    var footer = el("p", "daily-pick__source");
    if (item.list) {
      var sourceText = "来源：" + item.list;
      if (item.rank) sourceText += " · 第 " + item.rank + " 名";
      footer.appendChild(document.createTextNode(sourceText));
    }
    if (item.url) {
      var link = el("a", "daily-pick__link", "豆瓣条目 →");
      link.href = item.url;
      link.target = "_blank";
      link.rel = "noopener";
      footer.appendChild(link);
    }
    body.appendChild(footer);

    box.innerHTML = "";
    box.appendChild(coverWrap);
    box.appendChild(body);
    box.classList.add("daily-pick--ready");
  }

  function load(kind) {
    if (!cache[kind]) {
      cache[kind] = fetch(baseUrl + "assets/recommend/" + kind + "s.json").then(function (
        response
      ) {
        if (!response.ok) throw new Error("数据加载失败");
        return response.json();
      });
    }
    return cache[kind];
  }

  function init() {
    var boxes = document.querySelectorAll(".daily-pick[data-kind]");
    for (var i = 0; i < boxes.length; i++) {
      (function (box) {
        if (box.dataset.pickReady === "1") return;
        box.dataset.pickReady = "1";
        var kind = box.getAttribute("data-kind");
        load(kind)
          .then(function (data) {
            render(box, data);
          })
          .catch(function () {
            box.classList.add("daily-pick--error");
            var loading = box.querySelector(".daily-pick__loading");
            if (loading) loading.textContent = "今日推荐加载失败，请稍后再试。";
          });
      })(boxes[i]);
    }
  }

  if (typeof document$ !== "undefined" && document$.subscribe) {
    try {
      document$.subscribe(init);
    } catch (e) {
      /* 忽略 */
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
