(function () {
    function init() {
        var root = document.getElementById("reader-root");
        if (!root) {
            return;
        }

        var mangaId = root.getAttribute("data-manga-id");
        var chapterId = root.getAttribute("data-chapter-id");
        if (!mangaId || !chapterId) {
            return;
        }

        var pageElements = root.querySelectorAll("[data-page-number]");
        if (!pageElements.length) {
            return;
        }

        var lastSentPage = null;
        var visiblePages = {};

        function sendProgress(pageNumber) {
            if (pageNumber === lastSentPage) {
                return;
            }
            lastSentPage = pageNumber;

            var payload = {
                manga_id: parseInt(mangaId, 10),
                chapter_id: parseInt(chapterId, 10),
                page_number: pageNumber
            };

            fetch("/progress", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            }).catch(function (error) {
                console.error("Failed to send reading progress", error);
            });
        }

        function updateVisiblePages(entries) {
            entries.forEach(function (entry) {
                var target = entry.target;
                var pageNumber = parseInt(
                    target.getAttribute("data-page-number"),
                    10
                );
                if (!pageNumber) {
                    return;
                }
                var isVisible =
                    entry.isIntersecting && entry.intersectionRatio >= 0.5;
                visiblePages[pageNumber] = isVisible;
            });

            var currentPage = null;
            Object.keys(visiblePages).forEach(function (key) {
                var num = parseInt(key, 10);
                if (!visiblePages[num]) {
                    return;
                }
                if (currentPage === null || num > currentPage) {
                    currentPage = num;
                }
            });

            if (currentPage !== null) {
                sendProgress(currentPage);
            }
        }

        var observerOptions = { threshold: 0.5 };
        var observer = new IntersectionObserver(
            updateVisiblePages,
            observerOptions
        );

        pageElements.forEach(function (el) {
            observer.observe(el);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();

