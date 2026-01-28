/** @odoo-module **/

import { Wysiwyg } from '@web_editor/js/wysiwyg/wysiwyg';
import * as OdooEditorLib from "@web_editor/js/editor/odoo-editor/src/OdooEditor";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { isSelectionInSelectors, peek } from '@web_editor/js/editor/odoo-editor/src/utils/utils';

const closestElement = OdooEditorLib.closestElement;
const setSelection = OdooEditorLib.setSelection;
const parseHTML = OdooEditorLib.parseHTML;

patch(Wysiwyg.prototype, {
    _getPowerboxOptions() {
        const editorOptions = this.options;
        const categories = [{ name: _t('Banners'), priority: 65 },];
        const commands = [
            this._getBannerCommand(_t('Banner Info'), 'info', 'fa-info-circle', _t('Insert an info banner'), 24),
            this._getBannerCommand(_t('Banner Success'), 'success', 'fa-check-circle', _t('Insert a success banner'), 23),
            this._getBannerCommand(_t('Banner Warning'), 'warning', 'fa-exclamation-triangle', _t('Insert a warning banner'), 22),
            this._getBannerCommand(_t('Banner Danger'), 'danger', 'fa-exclamation-circle', _t('Insert a danger banner'), 21),
            {
                category: _t('Structure'),
                name: _t('Quote'),
                priority: 30,
                description: _t('Add a blockquote section'),
                fontawesome: 'fa-quote-right',
                isDisabled: () => !this.odooEditor.isSelectionInBlockRoot(),
                callback: () => {
                    this.odooEditor.execCommand('setTag', 'blockquote');
                },
            },
            {
                category: _t('Structure'),
                name: _t('Code'),
                priority: 20,
                description: _t('Add a code section'),
                fontawesome: 'fa-code',
                isDisabled: () => !this.odooEditor.isSelectionInBlockRoot(),
                callback: () => {
                    this.odooEditor.execCommand('setTag', 'pre');
                },
            },
            {
                category: _t('Basic blocks'),
                name: _t('Signature'),
                description: _t('Insert your signature'),
                fontawesome: 'fa-pencil-square-o',
                isDisabled: () => !this.odooEditor.isSelectionInBlockRoot(),
                callback: async () => {
                    const [user] = await this.orm.read(
                        'res.users',
                        [session.uid],
                        ['signature'],
                    );
                    if (user && user.signature) {
                        this.odooEditor.execCommand('insert', parseHTML(this.odooEditor.document, user.signature));
                    }
                },
            },
            // {
            //     category: _t('AI Tools'),
            //     name: _t('ChatGPT'),
            //     description: _t('Generate or transform content with AI.'),
            //     fontawesome: 'fa-magic',
            //     priority: 1,
            //     isDisabled: () => !this.odooEditor.isSelectionInBlockRoot(),
            //     callback: async () => this.openChatGPTDialog(),
            // },
        ];
        if (!editorOptions.inlineStyle) {
            commands.push(
                {
                    category: _t('Structure'),
                    name: _t('2 columns'),
                    priority: 13,
                    description: _t('Convert into 2 columns'),
                    fontawesome: 'fa-columns',
                    callback: () => this.odooEditor.execCommand('columnize', 2, editorOptions.insertParagraphAfterColumns),
                    isDisabled: () => {
                        if (!this.odooEditor.isSelectionInBlockRoot()) {
                            return true;
                        }
                        const anchor = this.odooEditor.document.getSelection().anchorNode;
                        const row = closestElement(anchor, '.o_text_columns .row');
                        return row && row.childElementCount === 2;
                    },
                },
                {
                    category: _t('Structure'),
                    name: _t('3 columns'),
                    priority: 12,
                    description: _t('Convert into 3 columns'),
                    fontawesome: 'fa-columns',
                    callback: () => this.odooEditor.execCommand('columnize', 3, editorOptions.insertParagraphAfterColumns),
                    isDisabled: () => {
                        if (!this.odooEditor.isSelectionInBlockRoot()) {
                            return true;
                        }
                        const anchor = this.odooEditor.document.getSelection().anchorNode;
                        const row = closestElement(anchor, '.o_text_columns .row');
                        return row && row.childElementCount === 3;
                    },
                },
                {
                    category: _t('Structure'),
                    name: _t('4 columns'),
                    priority: 11,
                    description: _t('Convert into 4 columns'),
                    fontawesome: 'fa-columns',
                    callback: () => this.odooEditor.execCommand('columnize', 4, editorOptions.insertParagraphAfterColumns),
                    isDisabled: () => {
                        if (!this.odooEditor.isSelectionInBlockRoot()) {
                            return true;
                        }
                        const anchor = this.odooEditor.document.getSelection().anchorNode;
                        const row = closestElement(anchor, '.o_text_columns .row');
                        return row && row.childElementCount === 4;
                    },
                },
                {
                    category: _t('Structure'),
                    name: _t('Remove columns'),
                    priority: 10,
                    description: _t('Back to one column'),
                    fontawesome: 'fa-columns',
                    callback: () => this.odooEditor.execCommand('columnize', 0),
                    isDisabled: () => {
                        if (!this.odooEditor.isSelectionInBlockRoot()) {
                            return true;
                        }
                        const anchor = this.odooEditor.document.getSelection().anchorNode;
                        const row = closestElement(anchor, '.o_text_columns .row');
                        return !row;
                    },
                },
                {
                    category: _t('Widgets'),
                    name: _t('Emoji'),
                    priority: 70,
                    description: _t('Add an emoji'),
                    fontawesome: 'fa-smile-o',
                    callback: () => {
                        this.showEmojiPicker();
                    },
                },
            );
        }
        if (editorOptions.allowCommandLink) {
            categories.push({ name: _t('Navigation'), priority: 40 });
            commands.push(
                {
                    category: _t('Navigation'),
                    name: _t('Link'),
                    priority: 40,
                    description: _t('Add a link'),
                    fontawesome: 'fa-link',
                    callback: () => {
                        this.toggleLinkTools({forceDialog: true});
                    },
                },
                {
                    category: _t('Navigation'),
                    name: _t('Button'),
                    priority: 30,
                    description: _t('Add a button'),
                    fontawesome: 'fa-link',
                    callback: () => {
                        this.toggleLinkTools({forceDialog: true});
                        // Force the button style after the link modal is open.
                        setTimeout(() => {
                            $(".o_link_dialog .link-style[value=primary]").click();
                        }, 150);
                    },
                },
            );
        }
        if (editorOptions.allowCommandImage || editorOptions.allowCommandVideo) {
            categories.push({ name: _t('Media'), priority: 50 });
        }
        if (editorOptions.allowCommandImage) {
            commands.push({
                category: _t('Media'),
                name: _t('Image'),
                priority: 40,
                description: _t('Insert an image'),
                fontawesome: 'fa-file-image-o',
                callback: () => {
                    this.openMediaDialog();
                },
            });
        }
        if (editorOptions.allowCommandVideo) {
            commands.push({
                category: _t('Media'),
                name: _t('Video'),
                priority: 30,
                description: _t('Insert a video'),
                fontawesome: 'fa-file-video-o',
                callback: () => {
                    this.openMediaDialog({noVideos: false, noImages: true, noIcons: true, noDocuments: true});
                },
            });
        }
        if (editorOptions.powerboxCategories) {
            categories.push(...editorOptions.powerboxCategories);
        }
        if (editorOptions.powerboxCommands) {
            commands.push(...editorOptions.powerboxCommands);
        }
        return {commands, categories};
    },
    _getBannerCommand(title, alertClass, iconClass, description, priority) {
        return {
            category: _t('Banners'),
            name: title,
            priority: priority,
            description: description,
            fontawesome: iconClass,
            isDisabled: () => isSelectionInSelectors('.o_editor_banner') || !this.odooEditor.isSelectionInBlockRoot(),
            callback: () => {
                const bannerElement = parseHTML(this.odooEditor.document, `
                    <div class="o_editor_banner o_not_editable lh-1 d-flex align-items-center alert alert-${alertClass} pb-0 pt-3" role="status" data-oe-protected="true">
                        <i class="fs-4 fa ${iconClass} mb-3" aria-label="${_t(title)}"></i>
                        <div class="w-100 px-3" data-oe-protected="false">
                            <p><br></p>
                        </div>
                    </div>
                `).childNodes[0];
                this.odooEditor.execCommand('insert', bannerElement);
                this.odooEditor.activateContenteditable();
                setSelection(bannerElement.querySelector('.o_editor_banner > div > p'), 0);
            },
        }
    },
});
