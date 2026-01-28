/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";
import { renderToElement } from "@web/core/utils/render";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.SurveyUploadFile = publicWidget.Widget.extend({
    selector: '.upload-files',

    init: function (parent, options) {
        this._super.apply(this, arguments);
        this.file_loaded = false;
        this.readonly = options.readonly;
        this.options = options;
    },

    start: function () {
        const self = this;
        const $inputFile = this.$target.find(".input-file");
        const ufiles = this.$target.find('input');

        const input_name = $inputFile.attr('data-name');
        const res_model = $inputFile.attr('res-model');
        const res_id = $inputFile.attr('data-res-id');
        const max_file_size = parseInt($inputFile.attr('max-file-size')) || 10;
        const maxFileSize = max_file_size * 1024 * 1024;  // 1 MB = 1048576 bytes

        let multifile = $inputFile.attr('multi-file') === "true";
        let show_del = $inputFile.attr('show-delete') === "true";
        let show_download = $inputFile.attr('show-download') === "true";

        if (this.readonly !== undefined) {
            show_del = !this.readonly;
            show_download = !this.readonly;
        }

        let files_ids = [];
        let totalfilesize = 0;
        let uploadedFiles = new Set();

        $inputFile.uploadFile({
            url: '/upload/attachment/onchange',
            fileName: 'attachments',
            multiple: multifile,
            maxFileCount: multifile ? 99 : 1,
            maxFileSize: maxFileSize,
            showDelete: show_del,
            showDownload: show_download,
            formData: { res_id, res_model },
            onSelect: function (files) {
                console.log('onSelect called with files:', files); // Debug log
                const fileArray = Array.from(files);
                const totalfilesize_select = fileArray.reduce((sum, file) => sum + file.size, 0);
            
                console.log('Current totalfilesize:', totalfilesize, 'New files size:', totalfilesize_select, 'Max allowed:', maxFileSize); // Debug log
            
                if ((totalfilesize + totalfilesize_select) > maxFileSize) {
                    alert(`The maximum size for all your attachments is ${max_file_size}MB. Please compress your files if required.`);
                    
                    // Clear the file input more thoroughly
                    const fileInput = $inputFile.find('input[type="file"]');
                    if (fileInput.length) {
                        fileInput.val('');
                        fileInput[0].value = ''; // Alternative clearing method
                    }
                    
                    // Also try to clear the uploadFile widget's internal state
                    setTimeout(function() {
                        const fileInput2 = $inputFile.find('input[type="file"]');
                        if (fileInput2.length) {
                            fileInput2.val('');
                            fileInput2[0].value = '';
                        }
                    }, 100);
            
                    // Don't add the rejected files to totalfilesize or uploadedFiles
                    return false;
                }
            
                // Only add to tracking variables if files are accepted
                fileArray.forEach(file => uploadedFiles.add(file.name));
                totalfilesize += totalfilesize_select;
                return true;
            },            
            
            deleteCallback: function (data, pd) {
                jsonrpc('/upload/attachment/delete', {
                    attachment_id: data,
                    res_id,
                    res_model
                }).then(function (response) {
                    if (response && response.length >= 2) {
                        const index = files_ids.indexOf(response[0]);
                        if (index > -1) {
                            files_ids.splice(index, 1);
                            totalfilesize -= response[1];
                            
                            // Find and remove the filename from uploadedFiles set
                            // Note: You might need to track filename separately if response[0] is not the filename
                            const fileToRemove = Array.from(uploadedFiles).find(filename => 
                                filename === response[0] || response[0].includes(filename)
                            );
                            if (fileToRemove) {
                                uploadedFiles.delete(fileToRemove);
                            }
                        }
                        ufiles.val(files_ids.toString());
                    } else {
                        console.error("Unexpected response format from delete API:", response);
                    }
                }).catch(function (error) {
                    console.error("Error in deleteCallback:", error);
                });
            },

            onLoad: function (obj) {
                jsonrpc('/upload/attachment/onload', {
                    res_model,
                    res_id,
                    files_ids: ufiles.val()
                }).then(function (data) {
                    for (let i = 0; i < data.length; i++) {
                        obj.createProgress(data[i].path, data[i].name, data[i].size);
                        files_ids.push(data[i].path);
                        totalfilesize += data[i].size;
                        uploadedFiles.add(data[i].name); // Add existing files to the set
                    }
                    ufiles.val(files_ids.toString());
                    if (data.length === 0) {
                        const $noattachment = self.$target.find('.no-attachment');
                        if ($noattachment.length > 0) {
                            $noattachment.show();
                        }
                    }
                    self.file_loaded = true;
                });
            },

            onSuccess: function (files, response, xhr, pd) {            
                files_ids.push(response);
                ufiles.val(files_ids.toString());
            },

            downloadCallback: function (filename, pd) {
                window.open(`/web/content/${filename}`, '_blank');
            },
            
            uploadButtonClass: "btn browse-btn",
            uploadStr: '<i class="fa fa-paperclip"></i>  &#160; Select Files',
            dragDropStr: "<span><b>Drag &amp; Drop Files Here</b></span>",
            sizeErrorStr: "is not allowed. Allowed Max size:",
            maxFileCountErrorStr: " is not allowed. Maximum allowed files are: ",
            statusBarWidth: 350,
            dragdropWidth: 350,
        });

        if (!show_del) {
            $inputFile.closest('form').hide();
        }

        this.$target.find('.btn-bs-file input').on('change', function (event) {
            const file_text = $(this).closest('.btn-bs-file').find('span');
            if (this.files.length > 1) {
                file_text.text(`${this.files.length} files selected`);
            } else if (this.files.length === 1) {
                file_text.text(this.files[0].name);
            } else {
                file_text.text('No file chosen');
            }
        });
    },
});