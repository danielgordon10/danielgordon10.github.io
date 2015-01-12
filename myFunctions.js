$(document).ready(function() { 
    // Helper functions
    var isSafari = /constructor/i.test(window.HTMLElement);
    var detectMob = function() {
        if( navigator.userAgent.match(/Android/i)
         || navigator.userAgent.match(/webOS/i)
         || navigator.userAgent.match(/iPhone/i)
         || navigator.userAgent.match(/iPad/i)
         || navigator.userAgent.match(/iPod/i)
         || navigator.userAgent.match(/BlackBerry/i)
         || navigator.userAgent.match(/Windows Phone/i)
         ){
            return true;
        }
        else {
            return false;
        }
    }
    
    var clamp = function(value, minNum, maxNum) {
        return Math.max(Math.min(value, maxNum), minNum);
    }
    if (isSafari) {
      $('#name').css('position', 'relative');
    }
    
    var minimizeTopAnimation = function() {
        if (!detectMob()) {
            $('#name_bar_container').addClass('top_animated');
            $('#name').addClass('top_animated');
            $('#im_container').addClass('top_animated');
            $('#profile').addClass('top_animated');
        }
    }
    var maximizeTopAnimation = function() {
        if (!detectMob()) {
            $('#name_bar_container').removeClass('top_animated');
            $('#name').removeClass('top_animated');
            $('#im_container').removeClass('top_animated');
            $('#profile').removeClass('top_animated');
        }
    }
    
    var isMinimized = false;
    var topShift = 0;
    $('body').scroll(function(){
        if (!isMinimized && $('#name').offset().top <= 0) {
            minimizeTopAnimation();
            isMinimized = true;
        } else if (isMinimized && $('#slide1').offset().top >= 250) {
            maximizeTopAnimation();
            isMinimized = false;
            topShift = 0;
            $('#name_bar_container').css('top', '0px');

        }
        
        if (isMinimized) {
            var currentTopShift = $('#name_bar_container').offset().top;
            if (currentTopShift != 0) {
                topShift -= currentTopShift;
                topShift = clamp(topShift, 0, Infinity);
                $('#name_bar_container').css('top', topShift + 'px');
            }
        }
        
    });
});
