/** @odoo-module **/
import { MenuItem, NavBar } from '@web/webclient/navbar/navbar';
import { patch } from "@web/core/utils/patch";
import { ErrorHandler, NotUpdatable } from "@web/core/utils/components";


var theme_style = 'default';

import { isMobileOS } from "@web/core/browser/feature_detection";
import { session } from "@web/session";
import { useService } from "@web/core/utils/hooks";
import { jsonrpc } from "@web/core/network/rpc_service";
import { onMounted } from "@odoo/owl";

var icon_style = 'standard';
var sidebar_collapse_style = '';
var search_style = '';
var enable_multi_tab = false

patch(NavBar.prototype, {

    //--------------------------------------------------------------------------
    // Public
    //--------------------------------------------------------------------------

    async setup() {
            super.setup()
            onMounted(() => {
                const spans = document.querySelectorAll('span');
                let targetSpan = null;
                spans.forEach(span => {
                  if (span.textContent.trim() === 'VANAESA') {
                    targetSpan = span;
                  }
                });
                if (targetSpan) {                  
                  var current_targetSpan =  targetSpan.parentElement.parentElement

                    $(current_targetSpan).next('.dropdown-menu-right').first().slideDown('slow');
                    $(current_targetSpan).parents('.dropdown-menu').first().find('.show_ul').slideUp(600)
                    $(current_targetSpan).parents('.dropdown-menu').first().find('.show_ul').css("display", "none !important")
                    $(current_targetSpan).parents('.dropdown-menu').first().find('.show_ul').removeClass('show_ul');

                    $(current_targetSpan).parents('.dropdown-menu').first().find('.sh_dropdown').removeClass('sh_dropdown');
                    $(current_targetSpan).parents('.dropdown-menu').first().find('.active').removeClass('active');
                    $(current_targetSpan).parents('.dropdown-menu').first().find('.sh_sub_dropdown').removeClass('sh_sub_dropdown');
                    $(current_targetSpan).next('.dropdown-menu').parents('.sh_dropdown_div').children('.dropdown-item').addClass('sh_dropdown');
                    $(current_targetSpan).next('.dropdown-menu').parents('.sh_dropdown_div').children('.dropdown-item').addClass('active');

                    var $subMenu = $(current_targetSpan).next('.dropdown-menu');
                    $subMenu.toggleClass('show_ul');
                }
                if (enable_multi_tab){
                   this.addmultitabtags()
                }
            });
        },
});