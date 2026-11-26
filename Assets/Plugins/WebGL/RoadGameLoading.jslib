mergeInto(LibraryManager.library, {
  RoadGameLoadingProgress: function (value) {
    var loading = window.RoadGameLoading;
    if (loading && typeof loading.memory === "function") loading.memory(HEAPU8.length);
    if (loading && typeof loading.progress === "function") {
      loading.progress(Math.max(0, Math.min(1, value)));
    }
  },
  RoadGameLoadingReady: function () {
    var bridge = window.RoadGameLoading;
    if (bridge && typeof bridge.memory === "function") bridge.memory(HEAPU8.length);
    // Unity calls after its ready frame is rendered. Let the browser present it before removing HTML.
    requestAnimationFrame(function () {
      var loading = window.RoadGameLoading;
      if (loading && typeof loading.ready === "function") loading.ready();
    });
  }
});
