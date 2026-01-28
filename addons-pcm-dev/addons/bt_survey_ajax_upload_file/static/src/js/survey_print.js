/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import SurveyPrintWidget from '@survey/js/survey_print';


SurveyPrintWidget.include({
    start: function () {
        var self = this;
        return this._super.apply(this, arguments).then(function () {
            $('div.survey-upload-files').each(function () {
                self._initFileWidget($(this));
            });
        });
    },
    _initFileWidget: function (ev) {
        var $result = this.$('.input-file');
        if ($result.length) {
            this.surveyFileWidget = new publicWidget.registry.SurveyUploadFile(ev, {'readonly': true});
            this.surveyFileWidget.attachTo(ev);
            $result.fadeIn(this.fadeInOutDelay);
        }
    },
})
