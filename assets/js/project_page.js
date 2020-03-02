
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
    if (lastPathSegment == 'index.html' || lastPathSegment == "") {
        jsonFile = "templates/zz_file_featured.json";
    } else {
        jsonFile = "templates/zz_file_order.json";
    }

    $.getJSON(jsonFile, function(orderData) {
        var projectsContainer = $("#projects-container");
        orderData.forEach(function(currVal, index) {
            projectsContainer.append('<div id="outerContainer' + index + '"></div>');
        });
        orderData.forEach(function(currVal, index) {
            $.getJSON("templates/" + currVal, function(data) {
                console.log('name ' + currVal + ' title ' + data.id + ' index ' + index);
                var element = $("#outerContainer" + index);
                if (data.pub_short.length > 0) {
                    publication = data.pub_short;
                } else {
                    publication = data.publication
                }
                if (data.vid_id.length > 0) {
                    element.append(
                          '<div class="bg-gray py-2" id="outer' + index + '">' +
                            '<div class="container bg-light">' +
                              '<div class="row shadow-sm">' +
                                '<div class="p-0 col-md-6">' +
                                  '<div class="embed-responsive embed-responsive-16by9">' +
                                    '<iframe class="embed-responsive-item" src="https://www.youtube.com/embed/' + data.vid_id + '?autoplay=0" allowfullscreen=""> </iframe>' +
                                  '</div>' +
                                '</div>' +
                                '<div class="col-md-6 px-3" onclick="location.href=\'projects/' + data.id + '.html\';" style="cursor: pointer;">' +
                                  '<div class="row">' +
                                    '<div class="col-md-12">' +
                                      '<h3 class="text-dark padding-top-1">' + data.title + '</h3>' +
                                      '<hr>' +
                                    '</div>' +
                                  '</div>' +
                                  '<div class="row">' +
                                    '<div class="col-md-12">' +
                                      '<p class="text-dark lead">' + data.authors + '<br><br>' +
                                        '<b id="pub' + index + '">' + publication + '</b>' +
                                      '</p>' +
                                    '</div>' +
                                  '</div>' +
                                '</div>' +
                              '</div>' +
                            '</div>' +
                          '</div>');
                } else {
                    element.append(
                      '<div class="bg-gray py-2" id="outer' + index + '">' +
                        '<div class="container bg-light">' +
                          '<div class="row shadow-sm">' +
                            '<div class="p-0 col-md-6">' +
                              '<img class="img-fluid d-block" src="images/projects/' + data.img_path + '">' +
                            '</div>' +
                            '<div class="col-md-6 px-3" onclick="location.href=\'projects/' + data.id + '.html\';" style="cursor: pointer;">' +
                              '<div class="row">' +
                                '<div class="col-md-12">' +
                                  '<h3 class="text-dark padding-top-1">' + data.title + '</h3>' +
                                  '<hr>' +
                                '</div>' +
                              '</div>' +
                              '<div class="row">' +
                                '<div class="col-md-12">' +
                                  '<p class="text-dark lead">' + data.authors + '<br><br>' +
                                    '<b id="pub' + index + '">' + publication + '</b>' +
                                  '</p>' +
                                '</div>' +
                              '</div>' +
                            '</div>' +
                          '</div>' +
                        '</div>' +
                      '</div>');
                }
                if (index == 0) {
                    $("#outer0").attr("id", "projects-card-first");
                } else if (index == orderData.length - 1) {
                    $("#outer" + index).attr("id", "projects-card-last");
                }
                if (publication.length == 0) {
                    $("#pub" + index).hide();
                }
            });
        });

    });

});
