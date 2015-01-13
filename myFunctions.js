(function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
(i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
})(window,document,'script','//www.google-analytics.com/analytics.js','ga');
ga('create', 'UA-57678938-1', 'auto');
ga('send', 'pageview');
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
    
    var minimizeTopAnimation = function() {
        //if (!detectMob()) {
            $('#name_bar_container').addClass('top_animated');
            $('#name_centerer').addClass('top_animated');
            $('#name').addClass('top_animated');
            $('#im_container').addClass('top_animated');
            $('#profile').addClass('top_animated');
        //}
    }
    var maximizeTopAnimation = function() {
        //if (!detectMob()) {
            $('#name_bar_container').removeClass('top_animated');
            $('#name_centerer').removeClass('top_animated');
            $('#name').removeClass('top_animated');
            $('#im_container').removeClass('top_animated');
            $('#profile').removeClass('top_animated');
        //}
    }
    
    var isMinimized = false;
    var topShift = 0;
    var shiftMax = 150;
    $('body').scroll(function(){
        // Moves background picture.
        var picHeight = $('#background_image').height();
        var offset = $('#background_bottom').offset().top;
        var shiftAmount = -1*clamp(shiftMax-offset*shiftMax/picHeight, 0, shiftMax);
        //console.log(offset*shiftMax/picHeight);
        /*
        var blurAmount = Math.min(Math.max(Math.round(blurMax-offset*blurMax/picHeight),0),blurMax);
        if (!isSafari && !detectMob()) {
          $('#title').css('filter', 'blur(' + blurAmount + 'px)');       
          $('#title').css('-webkit-filter', 'blur(' + blurAmount + 'px)');
          $('#title').css('-moz-filter', 'blur(' + blurAmount + 'px)');
          $('#title').css('-o-filter', 'blur(' + blurAmount + 'px)');
          $('#title').css('-ms-filter', 'blur(' + blurAmount + 'px)');
        }
        */
        if (!detectMob()) {
            $('#background_image').css('background-position', '0% ' + (shiftAmount)+ 'px');
        }   
    
        // Animation business
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
