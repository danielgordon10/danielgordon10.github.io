$(document).ready(function() {    
    var isSafari = /constructor/i.test(window.HTMLElement);
    if (isSafari) {
      $('#name').css('position', 'relative');
    }
    var blurMax = 10;
    var shiftMax = 150;
    $('body').scroll(function(){
        var picHeight = $('#slide1').height() - $('#background_image').height();
        var offset = $('#background_bottom').offset().top;
        var shiftAmount = -1*clamp(shiftMax-offset*shiftMax/picHeight, 0, shiftMax);
        //console.log(shiftAmount);
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
    });
    
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
});
