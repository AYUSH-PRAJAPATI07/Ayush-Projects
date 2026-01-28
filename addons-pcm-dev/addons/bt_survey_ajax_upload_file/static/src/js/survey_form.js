/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import SurveyFormWidget from '@survey/js/survey_form';


SurveyFormWidget.include({
    start: function () {
        var self = this;
        this.fadeInOutDelay = 400;
        return this._super.apply(this, arguments).then(function () {
            $('div.survey-upload-files').each(function () {
                self._initFileWidget($(this));
            });
        });
    },
    _initFileWidget: function (ev) {
        var $result = this.$('.input-file');
        var readonly = this.$('fieldset[disabled="disabled"]').length !== 0;
        if (this.readonly)
            readonly = this.readonly
        if ($result.length) {
            this.surveyFileWidget = new publicWidget.registry.SurveyUploadFile(ev, {'readonly': readonly});
            this.surveyFileWidget.attachTo(ev);
            $result.fadeIn(this.fadeInOutDelay);
        }
    },
    _onNextScreenDone: function (result, options) {
        var self = this;
        this._super.apply(this, arguments)
        if (result && !result.error) {
            $('div.survey-upload-files').each(function () {
                self._initFileWidget($(this));
            });
        }
    },
    _prepareSubmitValues: function (formData, params) {
        var self = this;
        this._super.apply(this, arguments)
        // Get all question answers by question type
        this.$('[data-question-type="file"]').each(function () {
            switch ($(this).data('questionType')) {
                case 'file':
                    params[this.name] = this.value;
                    break;
            }
        });
    },

});
