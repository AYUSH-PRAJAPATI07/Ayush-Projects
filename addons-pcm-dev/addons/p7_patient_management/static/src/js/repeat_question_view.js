/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import publicWidget from "@web/legacy/js/public/public_widget";
import SurveyFormWidget from '@survey/js/survey_form';
import { _t } from "@web/core/l10n/translation";
import {
    deserializeDate,
    deserializeDateTime,
    parseDateTime,
    parseDate,
    serializeDateTime,
    serializeDate,
} from "@web/core/l10n/dates";

SurveyFormWidget.include({
    setup() {
        this._super(...arguments);
        this.rpc = useService("rpc");
    },

    events: Object.assign({}, SurveyFormWidget.prototype.events, {
        'click .add-more-surgery-btn': '_onAddMoreQuestion',
        'click .js_del-question': '_removeQuesBlock',
        'click .continue_later': '_onSubmitPartial',
        'focusin .medicine-input': '_onFocusInput',
        'focusout .medicine-input': '_onFocusOutInput',
        'input .medicine-input': '_onFilterInput',
        'click .medicine-suggestion': '_onSelectMedicine',
        'click .create-new-medicine': '_onCreateNewMedicine',
    }),

    start: function () {
        var res = this._super.apply(this, arguments);
        return res;
    },

    _onFocusInput: function (event) {
        const questionId = event.target.getAttribute('name');
        this._showAllMedicines(questionId);
    },

    _onFocusOutInput: function (event) {
        const questionId = event.target.getAttribute('name');
        const suggestionBox = document.getElementById(`medicine-suggestion-${questionId}`);

        setTimeout(() => {
            suggestionBox.style.display = 'none';
        }, 200);
    },
    
    _onFilterInput: function (event) {
        const input = event.target;
        this._filterMedicines(input);
    },

    _onSelectMedicine: function (event) {
        const target = event.currentTarget;
        const questionId = target.closest('.js_question-wrap').getAttribute('data-question-id');
        const value = target.getAttribute('data-value');
        const input = document.getElementById(`medicine-input-${questionId}`);
        input.value = value;
        document.getElementById(`medicine-suggestion-${questionId}`).style.display = 'none';
    },

    _onCreateNewMedicine: function (event) {
        const target = event.currentTarget;
        const questionId = target.closest('.js_question-wrap').getAttribute('data-question-id');
        const input = document.getElementById(`medicine-input-${questionId}`);
        const newMedicineName = input.value.trim();
        if (newMedicineName) {
            const confirmCreate = confirm(`Create new medicine: "${newMedicineName}"?`);
            if (confirmCreate) {
                this._createNewMedicine(newMedicineName);
            }
        } else {
            alert("Please enter a valid medicine name.");
        }
    },

    _showAllMedicines: function (questionId) {
        const suggestionBox = document.getElementById(`medicine-suggestion-${questionId}`);
        this.rpc('/get_medicines', {query: '', limit: 10 }).then(medicines => {
            suggestionBox.innerHTML = '';
            medicines.forEach(medicine => {
                const displayName = (medicine.brand_name || '') + ' [' + (medicine.name || '') + ']';
                const item = document.createElement('li');
                item.classList.add('list-group-item', 'list-group-item-action', 'medicine-suggestion');
                item.setAttribute('data-value', displayName);
                item.textContent = displayName;
                suggestionBox.appendChild(item);
            });
    
            const createNewItem = document.createElement('li');
            createNewItem.classList.add('list-group-item', 'list-group-item-action', 'bg-light', 'text-primary', 'create-new-medicine');
            createNewItem.textContent = 'Create New';
            suggestionBox.appendChild(createNewItem);
    
            suggestionBox.style.display = 'block';
        }).catch(error => {
            console.error('Error fetching medicines:', error);
        });
    },
    

    _filterMedicines: function (input) {
        const questionId = input.getAttribute('name');
        const query = input.value.toLowerCase();
        const suggestionBox = document.getElementById(`medicine-suggestion-${questionId}`);
        // const items = suggestionBox.querySelectorAll('.list-group-item');
        if (query.trim() === "") {
            this._showAllMedicines(questionId);
            return;
        }

        this.rpc('/get_medicines', { query: query, limit: 10 }).then(medicines => {
            suggestionBox.innerHTML = '';
            medicines.forEach(medicine => {
                const displayName = (medicine.brand_name || '') + ' [' + (medicine.name || '') + ']';
                const item = document.createElement('li');
                item.classList.add('list-group-item', 'list-group-item-action', 'medicine-suggestion');
                item.setAttribute('data-value', displayName);
                item.textContent = displayName;
                suggestionBox.appendChild(item);
            });
    
            const createNewItem = document.createElement('li');
            createNewItem.classList.add('list-group-item', 'list-group-item-action', 'bg-light', 'text-primary', 'create-new-medicine');
            createNewItem.textContent = 'Create New';
            suggestionBox.appendChild(createNewItem);
    
            // suggestionBox.style.display = medicines.length ? 'block' : 'none';
            suggestionBox.style.display = 'block';
        }).catch(error => {
            console.error('Error fetching filtered medicines:', error);
        });
    },
    
    _createNewMedicine: function (newMedicine) {
        this.rpc("/create_medicine", {
            name: newMedicine,
        }).then(response => {
            if (response.status === "success") {
                alert(response.message);
                this._onFilterInput();
                this._onFocusOutInput();
            } else {
                alert('Failed to create new medicine. Please try again.');
            }
        }).catch(error => {
            console.error('Error:', error);
        });
    },

    showLimitedMedicines:function(input, questionId, medicines) {
        const dropdown = document.querySelector(`#dropdown-${questionId} select`);
        dropdown.innerHTML = `<option value="">Select your Medicine</option>`; // Reset dropdown
    
        // Show up to 3 records initially
        const limitedMedicines = medicines.slice(0, 3);
    
        // Append limited medicines to dropdown
        limitedMedicines.forEach(function (medicine) {
            dropdown.innerHTML += `<option value="${medicine.name}">${medicine.name}</option>`;
        });
    },
    
    filterMedicines:function(input, questionId, medicines) {
        const query = input.value.toLowerCase();
        const dropdown = document.querySelector(`#dropdown-${questionId} select`);
        dropdown.innerHTML = `<option value="">Select your Medicine</option>`; // Reset dropdown
        // Filter medicines based on input
        const filteredMedicines = medicines.filter(medicine =>
            medicine.name.toLowerCase().includes(query)
        );
    
        // Append filtered medicines to dropdown
        filteredMedicines.forEach(function (medicine) {
            dropdown.innerHTML += `<option value="${medicine.name}">${medicine.name}</option>`;
        });
    },

    _onAddMoreQuestion: function (event) {
        var $button = $(event.currentTarget);
        $button.prop('disabled', true);
        var questionId = $button.data('question-id');

        this.rpc("/survey/repeat_question", {
            question_id: questionId,
            answer_token: this.options.answerToken,
        }).then((result) => {
            console.log('RPC Success:',result.previousquestionId);
            if (result.status === "success") {
                var $chevronButtonRight = $(".oi-chevron-right");
                if ($chevronButtonRight.length) {
                    $chevronButtonRight.trigger("click");
                }
            }
        }).catch((error) => {
            console.error('RPC Error:', error);
        }).finally(() => {
            $button.prop('disabled', false);
        });
    },

    _insertNewQuestion: function(questions, previousQuestionId, length, medicines) {
        let headerQuestion = null;
        const nonHeaderQuestions = [];
        questions.forEach(question => {
            if (question.is_header) {
                headerQuestion = question;
            } else {
                nonHeaderQuestions.push(question);
            }
        });
        
        // Insert the header question first
        if (headerQuestion) {
            this._insertQuestion(headerQuestion, previousQuestionId, medicines,length);
            previousQuestionId = headerQuestion.id; // Update the previous question ID after inserting the header
        }
    
        // Insert the non-header questions
        nonHeaderQuestions.forEach(question => {
            this._insertQuestion(question, previousQuestionId, medicines,length);
            previousQuestionId = question.id; // Update the previous question ID after each question
        });
    },
    
    _insertQuestion: function(question, previousQuestionId, medicines,length) {
        const questionId = question.id;
        const questionTitle = question.title;
        const questionType = question.type;
        const isMedic = question.is_medic;
        const isHeader = question.is_header;
        const isMandatory = question.is_mandate;
        // const isValidate = question.is_validate;
        const isDuplicate = question.is_duplicated;

        const newQuestionElement = document.createElement('div');
        newQuestionElement.setAttribute('class', 'js_question-wrapper pb-4');
        newQuestionElement.setAttribute('id', questionId);
        newQuestionElement.setAttribute('data-required', isMandatory ? 'True' : 'False');
        newQuestionElement.setAttribute('data-duplicate', isDuplicate ? 'True' : 'False');
        newQuestionElement.setAttribute('data-constr-error-msg', 'This question requires an answer.');
        newQuestionElement.setAttribute('data-validation-error-msg', 'The answer you entered is not valid.');
        newQuestionElement.style.backgroundColor = question.colour;
        newQuestionElement.style.border = '2px solid #ddd';
        newQuestionElement.style.padding = '10px';
        newQuestionElement.style.borderRadius = '5px';
    
        let innerContent = `<div class="js_question-wrapper pb-4 ${isMandatory ? 'extra_right_margin' : ''}" id="${questionId}" data-required="${isMandatory}" data-duplicate="${isDuplicate ? 'True' : 'False'}" data-constr-error-msg="This question requires an answer">`;
        if (isHeader) {
            innerContent += `<div class="mb-4 d-flex justify-content-between align-items-center">
                                <h3 class="mb-0">
                                    <span class="text-break">${questionTitle}</span>
                                    ${isMandatory ? '<span class="text-danger">*</span>' : ''}
                                </h3>
                                <button type="button" class="btn btn-outline-danger ms-3 js_delete-question" data-question-id="${questionId}">
                                    <i class="fa fa-trash"></i>
                                </button>
                             </div>`;
            if (questionType === 'char_box') {
                if (isMedic) {
                    innerContent += `
                    <div class="js_question-wrap" data-question-id="${questionId}">
                        <input type="text"
                            class="form-control medicine-input o_survey_question_text_box bg-transparent rounded-0 p-0"
                            placeholder="Search the medicine..."
                            name="${questionId}" data-question-type="${questionType}" data-question-id="${questionId}"
                            id="medicine-input-${questionId}" />
                        <ul id="medicine-suggestion-${questionId}" class="list-group position-absolute mt-2" style="display: none; max-height: 150px; overflow-y: auto;">
                    `;

                    medicines.forEach(function (medicine) {
                        innerContent += `
                            <li class="list-group-item list-group-item-action medicine-suggestion" data-value="${medicine.name}">
                                ${medicine.name}
                            </li>`;
                    });

                    innerContent += `
                            <li class="list-group-item list-group-item-action bg-light text-primary create-new-medicine">
                                Create New
                            </li>
                        </ul>
                    </div>`;
                } else {
                    innerContent += `<input type="text" class="form-control o_survey_question_text_box bg-transparent rounded-0 p-0" name="${questionId}" value="" data-question-type="${questionType}">`;
                }
            }
            if (questionType === 'numerical_box') {
                innerContent += `<input type="number" step="any" class="form-control o_survey_question_numerical_box bg-transparent rounded-0 p-0" name="${questionId}" value="" data-question-type="${questionType}">`;
            }
            if (questionType === 'date') {
                innerContent += `<input type="date" class="form-control datetimepicker-input o_survey_question_date bg-transparent rounded-0 p-0" name="${questionId}" value="" data-question-type="${questionType}" >`;
            }
            if (questionType === 'datetime') {
                innerContent += `<input type="datetime-local" class="form-control datetimepicker-input o_survey_question_date bg-transparent rounded-0 p-0" name="${questionId}" value="" data-question-type="${questionType}">`;
            }
            if (questionType === 'text_box') {
                innerContent += `<textarea class="form-control o_survey_question_text_box bg-transparent rounded-0 p-0" rows="3" name="${questionId}" data-question-type="${questionType}"></textarea>`;
            }
        } else {
            innerContent += `<div class="mb-4">
                                <h3 class="mb-0">
                                    <span class="text-break">${questionTitle}</span>
                                    ${isMandatory ? '<span class="text-danger">*</span>' : ''}
                                </h3>
                             </div>`;
            if (questionType === 'char_box') {
                if (isMedic) {
                    innerContent += `
                    <div class="js_question-wrap" data-question-id="${questionId}">
                        <input type="text"
                            class="form-control medicine-input o_survey_question_text_box bg-transparent rounded-0 p-0"
                            placeholder="Search the medicine..."
                            name="${questionId}" data-question-type="${questionType}" data-question-id="${questionId}"
                            id="medicine-input" />
                        <ul id="medicine-suggestion" class="list-group position-absolute mt-2" style="display: none; max-height: 150px; overflow-y: auto;">
                    `;

                    medicines.forEach(function (medicine) {
                        innerContent += `
                            <li class="list-group-item list-group-item-action medicine-suggestion" data-value="${medicine.name}">
                                ${medicine.name}
                            </li>`;
                    });

                    innerContent += `
                            <li class="list-group-item list-group-item-action bg-light text-primary create-new-medicine">
                                Create New
                            </li>
                        </ul>
                    </div>`;
                } else {
                    innerContent += `<input type="text" class="form-control o_survey_question_text_box bg-transparent rounded-0 p-0" name="${questionId}" value="" data-question-type="${questionType}">`;
                }
            }
            if (questionType === 'numerical_box') {
                innerContent += `<input type="number" step="any" class="form-control o_survey_question_numerical_box bg-transparent rounded-0 p-0" name="${questionId}" value="" data-question-type="${questionType}">`;
            }
            if (questionType === 'date') {
                innerContent += `<input type="date" class="form-control datetimepicker-input o_survey_question_date bg-transparent rounded-0 p-0" name="${questionId}" value="" data-question-type="${questionType}" >`;
            }
            if (questionType === 'datetime') {
                innerContent += `<input type="datetime-local" class="form-control datetimepicker-input o_survey_question_date bg-transparent rounded-0 p-0" name="${questionId}" value="" data-question-type="${questionType}">`;
            }
            if (questionType === 'text_box') {
                innerContent += `<textarea class="form-control o_survey_question_text_box bg-transparent rounded-0 p-0" rows="3" name="${questionId}" data-question-type="${questionType}"></textarea>`;
            }
        }
    
        innerContent += `<div class="error-message text-danger mt-2"></div>`;
        innerContent += `</div>`;
        newQuestionElement.innerHTML = innerContent;

        const previousQuestionElement = document.getElementById(previousQuestionId);
        previousQuestionElement.after(newQuestionElement);

        // Attach delete event
        const deleteButton = newQuestionElement.querySelector('.js_delete-question');
        if (deleteButton) {
            deleteButton.addEventListener('click', () => {
                this._removeQuestionBlock(questionId, length);
            });
        }
    },
    
    _removeQuestionBlock: function(questionId, length) {
        const questionElement = document.getElementById(questionId);
        this.rpc("/survey/delete_question", {
            question_id: questionId,
            answer_token: this.options.answerToken,
        })
        if (questionElement) {
            // Get all the following sibling questions until another header or end
            let currentElement = questionElement.nextElementSibling;
            
            // Remove the current question (header)
            questionElement.remove();
            let removedCount = 0;
            // Remove all related questions until we hit another header or the end
            while (currentElement && removedCount < length) {
                const nextElement = currentElement.nextElementSibling;
                currentElement.remove();
                currentElement = nextElement;
                removedCount++;
            }
            var $chevronButtonLeft = $(".oi-chevron-left");
            if ($chevronButtonLeft.length) {
                $chevronButtonLeft.trigger("click");
            }
        } else {
            console.warn('Question element not found for deletion:', questionId);
        }
    },

    _removeQuesBlock: function(event) {
        event.preventDefault();
        var $target = $(event.currentTarget);
        var questionId = $target.data('question-id');
        var length = $target.data('question-length');
        this._removeQuestionBlock(questionId, length);
    },
    
    _onSubmit: function (event) {
        event.preventDefault();
        const options = {};
        const target = event.currentTarget;

        let isValid = true;           
        document.querySelectorAll('[data-required="True"][data-duplicate="True"]').forEach(function(questionElement) {
            const inputField = questionElement.querySelector('input, select, textarea');
            const errorMessageElement = questionElement.querySelector('.error-message');

            if (!inputField.value.trim()) {
                isValid = false;
                if (errorMessageElement) { // Check if the element exists before accessing it
                    errorMessageElement.textContent = questionElement.getAttribute('data-constr-error-msg');
                } else {
                    console.warn('Error message element not found for question:', questionElement); // Log if not found
                }
            } else {
                if (errorMessageElement) {
                    errorMessageElement.textContent = '';
                }
            }
        });
        
        if (!isValid) {
            event.preventDefault();
        }

        if (target.value === 'previous') {
            options.previousPageId = parseInt(target.dataset['previousPageId']);
        } else if (target.value === 'next_skipped') {
            options.nextSkipped = true;
        } else if (target.value === 'finish') {
            options.isFinish = true;
        } else if (target.value === 'continue_later') {
            options.continueLater = true;
        }
        this._submitForm(options);
    },

    _submitForm: async function (options) {
        var params = {};
        if (options.previousPageId) {
            params.previous_page_id = options.previousPageId;
        }
        if (options.nextSkipped) {
            params.next_skipped_page_or_question = true;
        }
        if (options.continueLater) {
            params.continue_later = true;
        }
        var route = "/survey/submit";
    
        if (this.options.isStartScreen) {
            route = "/survey/begin";
            if (this.options.questionsLayout === 'page_per_question') {
                this.$('.o_survey_main_title').fadeOut(400);
            }
        } else {
            var $form = this.$('form');
            var formData = new FormData($form[0]);

            if (!options.skipValidation) {
                if (!this._validateForm($form, formData)) {
                    return;
                }
            }
            
            // Add continue_later flag to formData if set
            if (options.continueLater) {
                formData.append('continue_later', true);
            }

            this._prepareSubmitValues(formData, params);

            var formdata = {};
            var key_question = formData.get("question_id");
            for (const pair of formData.entries()) {
                if (pair[0] == key_question) {
                    var values = formData.getAll(key_question);
                    if (Array.isArray(values) && values.length > 1) {
                        formdata[pair[0]] = values
                    } else {
                        formdata[pair[0]] = pair[1]
                    }
                } else {
                    formdata[pair[0]] = pair[1]
                }
            }

            const dataToSend = {
                "formdata": formdata,
            }

            await this.rpc("/survey/submit_question", {
                data: dataToSend,
            }).then((result) => {
                console.log('RPC Success:',result.status);
            })
        }

        // Submit the form as usual
        const submitPromise = this.rpc(`${route}/${this.options.surveyToken}/${this.options.answerToken}`, params);
    
        if (!this.options.isStartScreen && this.options.scoringType == 'scoring_with_answers_after_page') {
            const [correctAnswers] = await submitPromise;
            if (Object.keys(correctAnswers).length && document.querySelector('.js_question-wrapper')) {
                this._showCorrectAnswers(correctAnswers, submitPromise, options);
                return;
            }
        }
        if (!options.continueLater) {
            this._nextScreen(submitPromise, options);
        }
    },

    _onSubmitPartial: function (event) {
        var $button = $(event.currentTarget);
        $button.prop('disabled', true);
        event.preventDefault();
        const submitButton = document.querySelector('button[type="submit"]');
        this.rpc("/survey/partial-submit", {
            survey_token: this.options.surveyToken,
            answer_token: this.options.answerToken,
        }).then((result) => {
            if (submitButton) {
                submitButton.click();
            }
            // window.location.href = '/patient-dashboard';
            if (result && result.redirect_url) {
                window.location.href = result.redirect_url;
            }
        }).catch((error) => {
            console.error('RPC Error:', error);
        }).finally(() => {
            $button.prop('disabled', false);
        });
    },


    _onSubmit: function (event) {
        event.preventDefault();
        const options = {};
        const target = event.currentTarget;

        let isValid = true;           
        document.querySelectorAll('[data-required="True"][data-duplicate="True"]').forEach(function(questionElement) {
            const inputField = questionElement.querySelector('input, select, textarea');
            const errorMessageElement = questionElement.querySelector('.error-message');
            if (!inputField.value.trim()) {
                isValid = false;
                if (errorMessageElement) { // Check if the element exists before accessing it
                    errorMessageElement.textContent = questionElement.getAttribute('data-constr-error-msg');
                } else {
                    console.warn('Error message element not found for question:', questionElement); // Log if not found
                }
            } else {
                if (errorMessageElement) {
                    errorMessageElement.textContent = '';
                }
            }
        });

        const medicineQuestion = document.querySelector('.medicine-input');
        if (medicineQuestion) {
            const inputField = medicineQuestion;
            const enteredValue = inputField.value.trim().toLowerCase();

            const suggestionBox = document.getElementById(`medicine-suggestion-${inputField.name}`);
            const items = suggestionBox ? suggestionBox.querySelectorAll('.medicine-suggestion') : [];

            let matchFound = false;
            items.forEach(item => {
                const suggestionValue = item.getAttribute('data-value')?.toLowerCase();
                if (suggestionValue === enteredValue) {
                    matchFound = true;
                }
            });

            // if (!matchFound && enteredValue !== "") {
            //     const confirmCreate = confirm(`"${inputField.value}" is not in the list. Do you want to create it as new?`);
            //     if (confirmCreate && typeof this._createNewMedicine === "function") {
            //         this._createNewMedicine(inputField.value);
            //         matchFound = true;
            //     } else {
            //         return;
            //     }
            // }
        }
        
        if (!isValid) {
            event.preventDefault();
        }

        if (target.value === 'previous') {
            options.previousPageId = parseInt(target.dataset['previousPageId']);
        } else if (target.value === 'next_skipped') {
            options.nextSkipped = true;
        } else if (target.value === 'finish') {
            options.isFinish = true;
        } else if (target.value === 'continue_later') {
            options.continueLater = true;
        }
        this._submitForm(options);
    },

    _validateForm: function ($form, formData) {
        var self = this;
        var errors = {};
        var validationEmailMsg = _t("This answer must be an email address.");
        var validationDateMsg = _t("This is not a date");

        this._resetErrors();

        var data = {};
        formData.forEach(function (value, key) {
            data[key] = value;
        });

        var inactiveQuestionIds = this.options.sessionInProgress ? [] : this._getInactiveConditionalQuestionIds();

        $form.find('[data-question-type]').each(function () {
            var $input = $(this);
            var $questionWrapper = $input.closest(".js_question-wrapper");
            var questionId = $questionWrapper.attr('id');

            // If question is inactive, skip validation.
            if (inactiveQuestionIds.includes(parseInt(questionId))) {
                return;
            }

            var questionRequired = $questionWrapper.data('required');
            var constrErrorMsg = $questionWrapper.data('constrErrorMsg');
            var validationErrorMsg = $questionWrapper.data('validationErrorMsg');
            switch ($input.data('questionType')) {
                case 'char_box':
                    if (questionRequired && !$input.val()) {
                        errors[questionId] = constrErrorMsg;
                    } else if ($input.val() && $input.attr('type') === 'email' && !self._validateEmail($input.val())) {
                        errors[questionId] = validationEmailMsg;
                    } else {
                        var lengthMin = $input.data('validationLengthMin');
                        var lengthMax = $input.data('validationLengthMax');
                        var length = $input.val().length;
                        if (lengthMin && (lengthMin > length || length > lengthMax)) {
                            errors[questionId] = validationErrorMsg;
                        }
                    }
                    break;
                case 'text_box':
                    if (questionRequired && !$input.val()) {
                        errors[questionId] = constrErrorMsg;
                    }
                    break;
                case 'numerical_box':
                    if (questionRequired && !data[questionId]) {
                        errors[questionId] = constrErrorMsg;
                    } else {
                        var floatMin = $input.data('validationFloatMin');
                        var floatMax = $input.data('validationFloatMax');
                        var value = parseFloat($input.val());
                        if (floatMin && (floatMin > value || value > floatMax)) {
                            errors[questionId] = validationErrorMsg;
                        }
                    }
                    break;
                case 'date':
                case 'datetime':
                    if (questionRequired && !data[questionId]) {
                        errors[questionId] = constrErrorMsg;
                    } else if (data[questionId]) {
                        const [parse, deserialize] =
                            $input.data("questionType") === "date"
                                ? [parseDate, deserializeDate]
                                : [parseDateTime, deserializeDateTime];
                        const date = parse($input.val());
                        if (!date || !date.isValid) {
                            errors[questionId] = validationDateMsg;
                        } else {
                            const maxDate = deserialize($input.data('max-date'));
                            const minDate = deserialize($input.data('min-date'));
                            if (
                                (maxDate.isValid && date > maxDate) ||
                                (minDate.isValid && date < minDate)
                            ) {
                                errors[questionId] = validationErrorMsg;
                            }
                        }
                    }
                    break;
                case 'simple_choice_radio':
                case 'multiple_choice':
                    if (questionRequired) {
                        var $textarea = $questionWrapper.find('textarea');
                        if (!data[questionId]) {
                            errors[questionId] = constrErrorMsg;
                        } else if (data[questionId] === '-1' && !$textarea.val()) {
                            // if other has been checked and value is null
                            errors[questionId] = constrErrorMsg;
                        }
                    }
                    break;
                case 'matrix':
                    if (questionRequired) {
                        const subQuestionsIds = $questionWrapper.find('table').data('subQuestions');
                        // Highlight unanswered rows' header
                        const questionBodySelector = `div[id="${questionId}"] > .o_survey_question_matrix > tbody`;
                        subQuestionsIds.forEach((subQuestionId) => {
                            if (!(`${questionId}_${subQuestionId}` in data)) {
                                errors[questionId] = constrErrorMsg;
                                // self.el.querySelector(`${questionBodySelector} > tr[id="${subQuestionId}"] > th`).classList.add('bg-danger');
                                const headerCell = self.el.querySelector(`${questionBodySelector} > tr[id="${subQuestionId}"] > th`);
                                if (headerCell) {
                                    headerCell.classList.add('bg-danger');
                                }
                            }
                        });
                    }
                    break;
            }
        });
        if (Object.keys(errors).length > 0) {
            this._showErrors(errors);
            return false;
        }
        return true;
    },
});
