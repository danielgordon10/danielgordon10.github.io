/**
 * navbar-ontop.js 1.0.0
 * Add .navbar-ontop class to navbar when the page is scrolled to top
 * Make sure to add this script to the <head> of page to avoid flickering on load
 */

(function() {
    var scripts= document.getElementsByTagName('script');
    var path = scripts[scripts.length-1].src.split('?')[0];      // remove any ?query
    var homeDir = path.split('/').slice(0, -1).join('/') + '/../../';  // remove last filename part of path
    document.write("<style id='temp-navbar-ontop'>.navbar {opacity:0; transition: none !important}</style>");

    var className = "navbar-ontop";
    // we start hidden, to avoid flickering

    function update() {
        // toggle className based on the scrollTop property of document
        var nav = document.querySelector(".navbar");

        if (window.scrollY > 15) {
            nav.classList.remove(className);
        } else {
            nav.classList.add(className);
        }
    }
    $(document).ready(function() {
        $("#nav-placeholder").load(homeDir + "nav.html", function() {
            $(window).on('show.bs.collapse', function (e) {
                $(e.target).closest("." + className).removeClass(className);
            });

            $(window).on('hidden.bs.collapse', function (e) {
                update();
            });
            update();
            // still hacking to avoid flickering
            setTimeout(function() {
                document.querySelector("#temp-navbar-ontop").remove();
            });
            var nav = document.querySelector(".navbar");
            nav.style.opacity = 1;
            nav.style.transitionDuration = "0.5s";
            nav.style.webkitTransitionDuration = "0.5s";
        });
        window.addEventListener("scroll", function() {
            update();
        });
    });
})();