// Google analytics
(function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
(i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
})(window,document,'script','//www.google-analytics.com/analytics.js','ga');
ga('create', 'UA-57678938-1', 'auto');

$(document).ready(function() {
    function intersection_over_union (rect1, rect2) {
        var intersection = Math.max(0, Math.min(rect1[2], rect2[2]) - Math.max(rect1[0], rect2[0])) *Math.max(0, Math.min(rect1[3], rect2[3]) - Math.max(rect1[1], rect2[1]));
        var union = (rect1[2] - rect1[0]) * (rect1[3] - rect1[1]) +
            (rect2[2] - rect2[0]) * (rect2[3] - rect2[1]) -
            intersection;
        iou = intersection * 1.0 / Math.max(union, .00001);
        return iou.toFixed(3);
    }

    $(function() {
        var box1 = $('#box1').resizable().draggable();
        var box2 = $('#box2').resizable().draggable();
        var iou = $('#iou');
        var rect1 = Array(4).fill(0);
        var rect2 = Array(4).fill(0);
        


        var mouseMoveEvent = function(event) {
            // Move current box to front.
            //$('.box').not(this).css('z-index', '100');
            //$(this).css('z-index', '1000');
            
            var boundRect1=box1[0].getBoundingClientRect();
            var boundRect2=box2[0].getBoundingClientRect();
            rect1[0] = boundRect1.left;
            rect1[2] = boundRect1.right;
            rect1[1] = boundRect1.top;
            rect1[3] = boundRect1.bottom;

            rect2[0] = boundRect2.left;
            rect2[2] = boundRect2.right;
            rect2[1] = boundRect2.top;
            rect2[3] = boundRect2.bottom;
            iou.html("IOU: " + intersection_over_union(rect1, rect2));
        }
        mouseMoveEvent(null);
        box1.mousemove(mouseMoveEvent);
        box2.mousemove(mouseMoveEvent);
    });
});

