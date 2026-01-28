/* @odoo-module */

import { Message } from "@mail/core/common/message";
import { patch } from "@web/core/utils/patch";
import { useState, useEffect } from "@odoo/owl";

patch(Message.prototype, {
    setup() {
        super.setup();
        
        // Add state to store user_type
        this.authorState = useState({
            user_type: null,
            loading: false,
            loaded: false
        });

        // Effect to fetch user_type when message author changes
        useEffect(
            (authorId) => {
                if (authorId && !this.authorState.loaded) {
                    this.fetchAuthorUserType(authorId);
                }
            },
            () => [this.message.author?.id]
        );
    },

    /**
     * Fetch user_type from res.partner using RPC
     */
    async fetchAuthorUserType(partnerId) {
        if (this.authorState.loading || this.authorState.loaded) {
            return;
        }
        
        this.authorState.loading = true;
        
        try {
            const result = await this.rpc('/web/dataset/call_kw', {
                model: 'res.partner',
                method: 'read',
                args: [[partnerId], ['user_type']],
                kwargs: {}
            });
            
            if (result && result.length > 0) {
                let user_type_label = this.getUserTypeLabel(result[0].user_type);
                this.authorState.user_type = user_type_label;
                
                // Add user_type directly to message.author object for easy access
                if (this.message.author) {
                    this.message.author.user_type = user_type_label;
                }
                
                console.log('message.author.id:', this.message.author.id);
                console.log('message.author.user_type:', this.message.author.user_type);
            }
        } catch (error) {
            console.error('Error fetching user_type:', error);
        } finally {
            this.authorState.loading = false;
            this.authorState.loaded = true;
        }
    },

    getUserTypeLabel(user_type) {
        const USER_TYPES_LABEL = {
            'patient': 'Patient',
            'doctor': 'Anaesthelist',
            'admin': 'Administrator',
        };
        return USER_TYPES_LABEL[user_type];
    },

    /**
     * Getter to access user_type easily
     */
    get authorUserType() {
        return this.message.author?.user_type || this.authorState.user_type;
    },

    /**
     * Method to log author user type
     */
    logAuthorUserType() {
        console.log('message.author.id:', this.message.author?.id);
        console.log('message.author.user_type:', this.authorUserType);
    },

    /**
     * Override onMouseenter to demonstrate usage
     */
    onMouseenter() {
        super.onMouseenter();
        
        // Log user type when available
        if (this.authorUserType) {
            console.log('Author User Type on hover:', this.authorUserType);
        }
    },

    /**
     * Override onClick to demonstrate usage
     */
    async onClick(ev) {
        super.onClick(ev);
        
        // Force fetch user_type if not already loaded
        if (this.message.author?.id && !this.authorState.loaded) {
            await this.fetchAuthorUserType(this.message.author.id);
        }
        
        // Now you can access user_type
        if (this.message.author?.user_type) {
            console.log('Clicked message author user_type:', this.message.author.user_type);
        }
    },

    /**
     * Alternative method using search_read for better performance
     */
//     async fetchAuthorUserTypeOptimized(partnerId) {
//         if (this.authorState.loading || this.authorState.loaded) {
//             return;
//         }
        
//         this.authorState.loading = true;
        
//         try {
//             const result = await this.rpc('/web/dataset/call_kw', {
//                 model: 'res.partner',
//                 method: 'search_read',
//                 args: [
//                     [['id', '=', partnerId]], // domain
//                     ['user_type'] // fields
//                 ],
//                 kwargs: {
//                     limit: 1
//                 }
//             });
            
//             if (result && result.length > 0) {
//                 this.authorState.user_type = result[0].user_type;
                
//                 // Add user_type directly to message.author object
//                 if (this.message.author) {
//                     this.message.author.user_type = result[0].user_type;
//                 }
                
//                 console.log('message.author.id:', this.message.author.id);
//                 console.log('message.author.user_type:', this.message.author.user_type);
//             }
//         } catch (error) {
//             console.error('Error fetching user_type:', error);
//         } finally {
//             this.authorState.loading = false;
//             this.authorState.loaded = true;
//         }
//     },

//     /**
//      * Method to manually trigger user_type fetch
//      */
//     async loadAuthorUserType() {
//         if (this.message.author?.id) {
//             await this.fetchAuthorUserType(this.message.author.id);
//             return this.authorUserType;
//         }
//         return null;
//     },

//     /**
//      * Method to check if user_type is loaded
//      */
//     get isUserTypeLoaded() {
//         return this.authorState.loaded;
//     },

//     /**
//      * Method to check if user_type is loading
//      */
//     get isUserTypeLoading() {
//         return this.authorState.loading;
//     }
});