import logging
import os
from datetime import datetime
from odoo.tests.common import TransactionCase

class TestSendVerificationLink(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestSendVerificationLink, cls).setUpClass()
        
        # Get current date and time for the log file name
        now = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Use a directory where you have write permissions
        log_dir = '/home/suresh/fouri/custom/test_logs'
        os.makedirs(log_dir, exist_ok=True)
        cls.log_file = os.path.join(log_dir, f'test_log_{now}.log')
        
        # Set up logging
        # logging.basicConfig(filename=cls.log_file, level=logging.INFO)
        # cls.logger = logging.getLogger(__name__)
        # cls.logger.info('Test logging initialized.')
        
        cls.log_file_handler = open(cls.log_file, 'w')
        
        # Set up logging to use the open file handler
        cls.logger = logging.getLogger(__name__)
        cls.logger.setLevel(logging.INFO)
        cls.handler = logging.StreamHandler(cls.log_file_handler)
        cls.handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        cls.handler.setFormatter(formatter)
        cls.logger.addHandler(cls.handler)
        cls.logger.info('Test logging initialized.')

    def test_send_verification_link(self):
        # Example of logging within the test
        self.logger.info('Running test_send_verification_link')
        print('-------------------3333322222222222--------------')
        # Your test code here...
        self.logger.info('Finished test_send_verification_link')

    @classmethod
    def tearDownClass(cls):
        # Ensure that all log entries are flushed to the file and the file is properly closed
        cls.logger.info('Test logging completed.')
        cls.logger.info(f'Logging to: {cls.log_file}')
        logging.shutdown()
        print('-------------------44444433333333333--------------')
        super(TestSendVerificationLink, cls).tearDownClass()
