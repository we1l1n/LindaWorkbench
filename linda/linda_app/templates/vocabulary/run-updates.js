function set_percentage(percent) {
    var $ppc = $('.progress-pie-chart');
    $ppc.data('percent', percent);

    deg = 360*percent/100;
    if (percent > 50) {
        $ppc.addClass('gt-50');
    }

    $('.ppc-progress-fill').css('transform','rotate('+ deg +'deg)');
    $('.ppc-percents span').html(percent+'%');
}

function getEquivalent(v, vs) {
    for (var i=0; i<vs.length; i++) {
        if (vs[i].slug == v.slug) {
            return vs[i];
        }
    }

    return null;
}

function increaseUpdateStep(text) {
    if (!hasRunUpdate) {
        hasRunUpdate = true;
        $("#initial-fetch").remove();
        $('.progress-pie-chart').show();
    }

    VocabularyChangesCounter++;

    $(".vocabulary-updates .info").html(text);
    set_percentage(Math.round(VocabularyChangesCounter*100.0/VocabularyChangesTotal));

    if (VocabularyChangesCounter == VocabularyChangesTotal) { //updates finished
        $('.progress-pie-chart').hide();
        $(".vocabulary-updates .info").html('Vocabularies updated succesfully [' + new_vocabs.length + ' new, ' +
                                            changed_vocabs.length + ' changed, ' + deleted_vocabs.length + ' deleted]');
    }
}

function createVocabulary(new_vocab) {
    $.ajax({
        url: '/api/vocabulary-repo/vocabularies/' + new_vocab.id + '/',
        type: "GET",
        success: function(server_response, textStatus, jqXHR) {
            $.ajax({
                url: '/api/vocabularies/',
                type: "POST",
                data: {
                    vocab_data: JSON.stringify(server_response),
                    csrfmiddlewaretoken: '{{csrf_token}}'
                },
                success: function(vs_repo, textStatus, jqXHR) {
                    increaseUpdateStep('Created vocabulary ' + new_vocab.slug);
                },
                error: function (jqXHR, textStatus, errorThrown) {
                    increaseUpdateStep('Error creating vocabulary ' + new_vocab.slug);
                }
            });
        },
        error: function (jqXHR, textStatus, errorThrown) {
           increaseUpdateStep('Error creating vocabulary ' + new_vocab.slug);
        }
    });
}

function updateVocabulary(old_vocab, new_vocab) {
    $.ajax({
        url: '/api/vocabulary-repo/vocabularies/' + new_vocab.id + '/',
        type: "GET",
        success: function(server_response, textStatus, jqXHR) {
            $.ajax({
                url: '/api/vocabularies/' + old_vocab.id + '/update/',
                type: "POST",
                data: {
                    vocab_data: JSON.stringify(server_response),
                    csrfmiddlewaretoken: '{{csrf_token}}'
                },
                success: function(vs_repo, textStatus, jqXHR) {
                    increaseUpdateStep('Updated vocabulary ' + old_vocab.slug);
                },
                error: function (jqXHR, textStatus, errorThrown) {
                    increaseUpdateStep('Error updating vocabulary ' + old_vocab.slug);
                }
            });
        },
        error: function (jqXHR, textStatus, errorThrown) {
            increaseUpdateStep('Error updating vocabulary ' + old_vocab.slug);
        }
    });
}

function deleteVocabulary(old_vocab) {
    $.ajax({
        url: '/api/vocabularies/' + old_vocab.id + '/delete/',
        type: "POST",
        data: {
            csrfmiddlewaretoken: '{{ csrf_token }}'
        },
        success: function(vs_repo, textStatus, jqXHR) {
            increaseUpdateStep('Deleted vocabulary ' + old_vocab.slug);
        },
        error: function (jqXHR, textStatus, errorThrown) {
            increaseUpdateStep('Error deleting vocabulary ' + old_vocab.slug);
        }
    });
}

$(function(){
    set_percentage(0);
    hasRunUpdate = false;

    //retrieve local vocabularies
    $.ajax({
        url: '/api/vocabularies/versions/',
        type: "GET",

        success: function(vs_local, textStatus, jqXHR) {
            //retrieve repositiory vocabularies
            $.ajax({
                url: '/api/vocabulary-repo/vocabularies/versions/',
                type: "GET",

                success: function(vs_repo, textStatus, jqXHR) {
                    $(".vocabulary-updates .info").html('Detecting changes...');

                    //detect changes
                    VocabularyChangesTotal = 0;

                    new_vocabs = new Array();
                    changed_vocabs = new Array();
                    deleted_vocabs = new Array();

                    vs_local.forEach(function(v_local) {
                        v_repo = getEquivalent(v_local, vs_repo);

                        if (v_repo && (v_local.version != v_repo.version)) { //find changed/removed vocabularies -- ignore locals-only
                            VocabularyChangesTotal++;
                            if (v_repo.version == "DELETED") {
                                deleted_vocabs.push(v_local);
                            } else {
                                changed_vocabs.push({"old_vocab": v_local, "new_vocab": v_repo});
                            }
                        }
                    });

                    vs_repo.forEach(function(v_repo) {
                        v_local = getEquivalent(v_repo, vs_local);

                        if (!v_local) { //new vocabularies
                            VocabularyChangesTotal++;
                            new_vocabs.push(v_repo);
                        }
                    });

                    if (VocabularyChangesTotal == 0) { //no changes detected
                        $("#initial-fetch").remove();
                        $(".vocabulary-updates .info").html('Local repository is already up to date.');
                        return;
                    }

                    VocabularyChangesCounter = 0;
                    $(".vocabulary-updates .info").html('Downloading updates...');

                    //applying changes
                    var cnt = 0;

                    for (var i=0; i<new_vocabs.length; i++) { //create new vocabularies
                        createVocabulary(new_vocabs[i]);
                    }

                    for (var i=0; i<changed_vocabs.length; i++) { //update existing vocabularies
                        updateVocabulary(changed_vocabs[i].old_vocab, changed_vocabs[i].new_vocab);
                    }

                    for (var i=0; i<deleted_vocabs.length; i++) { //delete vocabularies
                        deleteVocabulary(deleted_vocabs[i]);
                    }
                },
                error: function (jqXHR, textStatus, errorThrown) {
                    $("#initial-fetch").remove();
                    $(".vocabulary-updates .info").html('Could not get vocabulary list from repository server.');
                }

            });
        },

        error: function (jqXHR, textStatus, errorThrown) {
            $("#initial-fetch").remove();
            $(".vocabulary-updates .info").html('Could not get local vocabulary list. Please try again later.');
        }
    });
});