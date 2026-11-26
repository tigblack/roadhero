// QA bridge for automated browser checks. Silent for players: it only answers when the test page itself defined
// window.RoadGameQA before the game started (a test harness does that; the published page never does).
mergeInto(LibraryManager.library, {
  RoadGameQAEnabled: function () {
    return (typeof window !== "undefined" && window.RoadGameQA && typeof window.RoadGameQA.report === "function") ? 1 : 0;
  },
  RoadGameQAReport: function (json) {
    var qa = window.RoadGameQA;
    if (!qa || typeof qa.report !== "function") return;
    var s = UTF8ToString(json);
    try { qa.report(s, HEAPU8.length); } catch (e) { }
  }
});
