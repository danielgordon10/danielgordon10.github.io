
$(document).ready(function() {

    function addOrHide(text, element) {
        if (text.length > 0) {
            element.html(text);
        } else {
            element.hide();
        }
    }


    var href = document.location.href;
    var lastPathSegment = href.substr(href.lastIndexOf('/') + 1);
    var lastPathSegment = lastPathSegment.substring(0, lastPathSegment.length - 4) + "json";
    $.getJSON("../project_info/" + lastPathSegment, function(data) {
        $("#page-title").html(data.title);
        if (data.hasOwnProperty("title_project_page") && data.title_project_page.length > 0) {
            $("#title-text").html(data.title_project_page);
        } else {
            $("#title-text").html(data.title);
        }
        $("#abstract").html(data.abstract);
        addOrHide(data.authors, $("#authors"));
        if (data.publication.length > 0) {
            $("#publication").html(data.publication);
        } else {
            $("#publication").hide();
            $("#authors").css("margin-bottom", "");
        }
        addOrHide(data.bibtex, $("#bibtex"));

        if (data.vid_id.length > 0) {
            $("#vid-frame").attr("src", "https://www.youtube.com/embed/" + data.vid_id + "?autoplay=0");
            $("#image-container").hide();
        } else {
            $("#vid-container").hide();
            if (data.img_path.length > 0) {
                $("#paper-image").attr("src", "../images/projects/" + data.img_path);
            } else {
                $("#image-container").hide();
            }
        }

        data.buttons.forEach(function(currVal, index) {
            var buttonElement = $("<a class='btn btn-lg mx-2 text-uppercase btn-info project-page-btn', target='_blank'></a>");
            buttonElement.attr("href", currVal[1]);
            buttonElement.html(currVal[0]);
            $("#button-div").append(buttonElement);
        });
    });


});
