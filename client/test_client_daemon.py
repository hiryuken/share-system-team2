import hashlib
import unittest
import os
import shutil
import json

import httpretty
import client_daemon


start_dir = os.getcwd()

TEST_DIR = 'daemon_test'
LAST_TIMESTAMP = 'last_timestamp'
GLOBAL_MD5 = 'global_md5'
SERVER_TIMESTAMP = 1

base_dir_tree = {
    # <filepath>: (<timestamp>, <md5>)
    'ciao.txt': (3, 'md5md6'),
    'carlo.txt': (2, 'md6md6'),
    './Pytt/diaco.txt': (12, '7645jghkjhdfk'),
    'pasquale.cat': (12, 'khgraiuy8qu4l'),
    'carlo.buo': (14, 'rfhglkr94094580'),
}


def folder_modified():
    """
    Return True to indicate that sharing folder is modified during daemon is down
    """
    return True


def folder_not_modified():
    """
    Return True to indicate that sharing folder is modified during daemon is down
    """
    return False


def setup_test_dir():
    """
    Create (if needed) <TEST_DIR> directory starting from current directory and change current directory to the new one.
    """
    try:
        os.mkdir(TEST_DIR)
    except OSError:
        pass

    os.chdir(TEST_DIR)


def tear_down_test_dir():
    """
    Return to initial directory and remove the <TEST_DIR> one.
    """
    os.chdir(start_dir)
    shutil.rmtree(TEST_DIR)


def create_file(file_path, content=''):
    """
    Write <content> (default: '') into <file_path> and return the float timestamp
    of created file, also creating inner directories if needed.
    :param file_path: str
    :param content: str
    :return: float
    """
    print 'Creating "{}"'.format(file_path)
    dirname = os.path.dirname(file_path)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    assert os.path.isdir(dirname), '{} must be a directory'.format(dirname)

    with open(file_path, 'w') as fp:
        fp.write(content)
    return os.path.getmtime(file_path)


class FileFakeEvent(object):
    """
    Class that simulates a file related event sent from watchdog.
    Actually create <src_path> and <dest_path> attributes and the file in disk.
    """

    def __init__(self, src_path, content='', dest_path=None):
        self.src_path = src_path
        create_file(self.src_path, content=content)
        self.dest_path = dest_path


import test_utils


class TestDaemonCmdManagerConnection(unittest.TestCase):
    def setUp(self):
        self.client_daemon = client_daemon.Daemon()
        self.client_daemon.create_observer()
        self.socket = test_utils.FakeSocket()

    def test_get_cmdmanager_request(self):
        command = {'shutdown': ()}
        json_data = json.dumps(command)
        self.socket.set_response(json_data)

        self.assertEquals(self.client_daemon._get_cmdmanager_request(self.socket), json.loads(json_data))

    def test_set_cmdmanager_response(self):
        response = 'testtestetst'
        self.assertEqual(self.client_daemon._set_cmdmanager_response(self.socket, response),
                         json.dumps({'message': response}))


class TestClientDaemon(unittest.TestCase):
    def setUp(self):
        self.client_daemon = client_daemon.Daemon()
        self.client_daemon.create_observer()

    def test_sync_process_directory_not_modified1(self):
        """
        Test the case: (it must do nothing)
        Directory not modified,
        timestamp client == timestamp server
        """
        self.client_daemon._is_directory_modified = folder_not_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: server_timestamp, GLOBAL_MD5: ''}
        files = base_dir_tree.copy()
        self.client_daemon.client_snapshot = base_dir_tree.copy()
        self.assertEqual(
            self.client_daemon._sync_process(server_timestamp, files),
            []
        )

    def test_sync_process_directory_not_modified2(self):
        """
        Test the case: (it must download the file)
        Directory not modified,
        timestamp client < timestamp server
        new file on server and not in client
        """
        self.client_daemon._is_directory_modified = folder_not_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

        files = base_dir_tree.copy()
        files.update({'new': (18, 'md5md6jkshkfv')})
        self.client_daemon.client_snapshot = base_dir_tree.copy()

        self.assertEqual(
            self.client_daemon._sync_process(server_timestamp, files),
            [('download', 'new'), ]
        )

    def test_sync_process_directory_not_modified3(self):
        """
        Test the case: (it must copy or rename the file)
        Directory not modified,
        timestamp client < timestamp server
        new file on server and in client but with different filepath
        """
        self.client_daemon._is_directory_modified = folder_not_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

        files = base_dir_tree.copy()
        files.update({'new': (18, 'md5md6')})
        self.client_daemon.client_snapshot = base_dir_tree.copy()

        self.assertEqual(
            self.client_daemon._sync_process(server_timestamp, files),
            []
        )

    def test_sync_process_directory_not_modified4(self):
        """
        Test the case: (it must download the file)
        Directory not modified,
        timestamp client < timestamp server
        file modified on server
        """
        self.client_daemon._is_directory_modified = folder_not_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

        files = base_dir_tree.copy()
        self.client_daemon.client_snapshot = base_dir_tree.copy()
        files['carlo.txt'] = (server_timestamp, 'md5 diverso')

        self.assertEqual(
            self.client_daemon._sync_process(server_timestamp, files),
            [('download', 'carlo.txt'), ]
        )

    def test_sync_process_directory_not_modified5(self):
        """
        Test the case: (it must delete the file on client)
        Directory not modified,
        timestamp client < timestamp server
        file is missing on server
        """
        self.client_daemon._is_directory_modified = folder_not_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

        files = base_dir_tree.copy()
        self.client_daemon.client_snapshot = base_dir_tree.copy()
        self.client_daemon.client_snapshot.update({'carlito.txt': (1, 'jkdhlghkg')})

        self.assertEqual(self.client_daemon._sync_process(server_timestamp, files), [])

    def test_sync_process_directory_modified1(self):
        """
        Test the case: (it must do nothing)
        Directory modified,
        timestamp client == timestamp server
        client is already synchronized with server
        """
        self.client_daemon._is_directory_modified = folder_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: server_timestamp, GLOBAL_MD5: ''}

        files = base_dir_tree.copy()
        self.client_daemon.client_snapshot = base_dir_tree.copy()

        self.assertEqual(
            self.client_daemon._sync_process(server_timestamp, files),
            []
        )

    def test_sync_process_directory_modified2(self):
        """
        Test the case: (it must delete the file on server)
        Directory modified,
        timestamp client == timestamp server
        new file on server and not on client
        """
        self.client_daemon._is_directory_modified = folder_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: server_timestamp, GLOBAL_MD5: ''}

        files = base_dir_tree.copy()
        self.client_daemon.client_snapshot = base_dir_tree.copy()
        files.update({'new': (18, 'md5md6jkshkfv')})

        self.assertEqual(
            self.client_daemon._sync_process(server_timestamp, files),
            [('delete', 'new')]
        )

    def test_sync_process_directory_modified3(self):
        """
        Test the case: (it must modify the file on server)
        Directory modified,
        timestamp client == timestamp server
        file modified
        """
        self.client_daemon._is_directory_modified = folder_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: server_timestamp, GLOBAL_MD5: ''}

        files = base_dir_tree.copy()
        self.client_daemon.client_snapshot = base_dir_tree.copy()
        files['carlo.txt'] = (server_timestamp, 'md5 diverso')

        self.assertEqual(
            self.client_daemon._sync_process(server_timestamp, files),
            [('modify', 'carlo.txt')]
        )

    def test_sync_process_directory_modified4(self):
        """
        Test the case: (it must upload the file on server)
        Directory modified,
        timestamp client == timestamp server
        new file in client and not on server
        """
        self.client_daemon._is_directory_modified = folder_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: server_timestamp, GLOBAL_MD5: ''}

        files = base_dir_tree.copy()
        self.client_daemon.client_snapshot = base_dir_tree.copy()
        files.pop('carlo.txt')

        self.assertEqual(
            self.client_daemon._sync_process(server_timestamp, files),
            [('upload', 'carlo.txt')]
        )

    def test_sync_process_directory_modified5(self):
        """
        Test the case: (it must download the file)
        Directory modified,
        timestamp client < timestamp server
        new file on server and not in client
        file timestamp > client timestamp
        """
        self.client_daemon._is_directory_modified = folder_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

        files = base_dir_tree.copy()
        self.client_daemon.client_snapshot = base_dir_tree.copy()
        files.update({'new': (18, 'md5md6jkshkfv')})

        self.assertEqual(
            self.client_daemon._sync_process(server_timestamp, files),
            [('download', 'new')]
        )

    def test_sync_process_directory_modified6(self):
        """
        Test the case: (it must delete the file)
        Directory modified,
        timestamp client < timestamp server
        new file on server and not in client
        file timestamp < client timestamp
        """
        self.client_daemon._is_directory_modified = folder_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

        files = base_dir_tree.copy()
        self.client_daemon.client_snapshot = base_dir_tree.copy()
        files.update({'new': (16, 'md5md6jkshkfv')})

        self.assertEqual(
            self.client_daemon._sync_process(server_timestamp, files),
            [('delete', 'new')]
        )

    def test_sync_process_directory_modified7(self):
        """
        Test the case: (it must copy or move the file)
        Directory modified,
        timestamp client < timestamp server
        new file on server and in client
        """
        self.client_daemon._is_directory_modified = folder_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

        files = base_dir_tree.copy()
        self.client_daemon.client_snapshot = base_dir_tree.copy()
        files.update({'new': (16, 'md5md6')})

        self.assertEqual(
            self.client_daemon._sync_process(server_timestamp, files),
            []
        )

    def test_sync_process_directory_modified8(self):
        """
        Test the case: (it must modify the file on server)
        Directory modified,
        timestamp client < timestamp server
        file modified
        file timestamp < client timestamp
        """
        self.client_daemon._is_directory_modified = folder_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

        files = base_dir_tree.copy()
        self.client_daemon.client_snapshot = base_dir_tree.copy()
        files['carlo.txt'] = (16, 'md5md6jkshkfv')

        self.assertEqual(
            self.client_daemon._sync_process(server_timestamp, files),
            [('modify', 'carlo.txt')]
        )

    def test_sync_process_directory_modified9(self):
        """
        Test the case: (there is a conflict, so it upload the file on server with ".conflicted" extension)
        Directory modified,
        timestamp client < timestamp server
        file modified
        file timestamp > client timestamp
        """
        self.client_daemon._is_directory_modified = folder_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

        files = base_dir_tree.copy()
        self.client_daemon.client_snapshot = base_dir_tree.copy()
        files['carlo.txt'] = (18, 'md5md6jkshkfv')

        self.assertEqual(
            self.client_daemon._sync_process(server_timestamp, files),
            [('upload', ''.join(['carlo.txt', '.conflicted']))]
        )

    def test_sync_process_directory_modified10(self):
        """
        Test the case: (it upload the file on server)
        Directory modified,
        timestamp client < timestamp server
        new file in client and not on server
        """
        self.client_daemon._is_directory_modified = folder_modified

        server_timestamp = 18
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: 17, GLOBAL_MD5: ''}

        files = base_dir_tree.copy()
        self.client_daemon.client_snapshot = base_dir_tree.copy()
        files.pop('carlo.txt')

        self.assertEqual(
            self.client_daemon._sync_process(server_timestamp, files),
            [('upload', 'carlo.txt')]
        )


class TestClientDaemonOnEvents(unittest.TestCase):
    """
    Test the "on_<something>" client daemon, triggered by watchdog.
    """
    CONFIG_DIR = os.path.join(os.environ['HOME'], '.PyBox')
    CONFIG_FILEPATH = os.path.join(CONFIG_DIR, 'daemon_config')
    LOCAL_DIR_STATE_PATH = os.path.join(CONFIG_DIR, 'local_dir_state')

    def setUp(self):
        # Create and go into the test directory
        setup_test_dir()
        httpretty.enable()

        # self.cm = ConnectionManager()
        with open(self.CONFIG_FILEPATH) as fo:
            self.cfg = json.load(fo)

        self.auth = self.cfg['user'], self.cfg['pass']
        self.cfg['server_address'] = "http://localhost:5000"

        # create this auth testing
        self.authServerAddress = "http://" + self.cfg['user'] + ":" + self.cfg['pass']
        self.base_url = self.cfg['server_address'] + self.cfg['api_suffix']
        self.files_url = self.base_url + 'files/'
        self.actions_url = self.base_url + 'actions/'
        self.local_dir_state_path = self.cfg['local_dir_state_path']
        self.sharing_path = self.cfg['sharing_path']

        # Instantiate the daemon
        self.client_daemon = client_daemon.Daemon()
        self.client_daemon.create_observer()
        # Injecting a fake client snapshot
        md5 = '50abe822532a06fb733ea3bc089527af'
        ts = 1403878699
        path = 'dir/file.txt'
        self.client_daemon.client_snapshot = {path: [ts, md5]}
        self.client_daemon.local_dir_state = {LAST_TIMESTAMP: ts, GLOBAL_MD5: md5}

    def tearDown(self):
        httpretty.disable()
        httpretty.reset()
        # Remove the test directory.
        tear_down_test_dir()

    def test_md5_of_client_snapshot(self, verbose=1):
        """
        Test the Daemons function
        """
        md5hash = hashlib.md5()

        for path, time_md5 in self.client_daemon.client_snapshot.items():
            # extract md5 from tuple. we don't need hexdigest it's already md5
            md5hash.update(time_md5[1])
            md5hash.update(path)

        response_of_function = self.client_daemon.md5_of_client_snapshot()
        self.assertNotEqual(response_of_function, '50abe822532a06fb733ea3bc089527af')
        self.assertEqual(response_of_function, md5hash.hexdigest())

    @httpretty.activate
    def test_on_created(self):
        """
        Test on_created method of daemon when a new file is created.
        """
        start_state = self.client_daemon.local_dir_state.copy()
        ts1 = start_state[LAST_TIMESTAMP]
        ts2 = ts1 + 60  # arbitrary value

        # new file I'm going to create in client sharing folder
        new_path = 'created_file.txt'

        url = self.files_url + new_path
        httpretty.register_uri(httpretty.POST, url, status=201,
                               body='{"server_timestamp":%d}' % ts2,
                               content_type="application/json")

        abs_path = os.path.join(self.client_daemon.cfg['sharing_path'], new_path)
        event = FileFakeEvent(abs_path)

        self.client_daemon.on_created(event)
        # test that the new path is in the client_snapshot
        self.assertIn(new_path, self.client_daemon.client_snapshot)
        # simply check that local_dir_state is changed
        self.assertNotEqual(start_state, self.client_daemon.local_dir_state)

        # # daemon.local_dir_state should be a dict
        self.assertIsInstance(self.client_daemon.local_dir_state, dict)
        # last_timestamp should be an int
        self.assertIsInstance(self.client_daemon.local_dir_state[LAST_TIMESTAMP], int)
        # test exact value of timestamp
        self.assertEqual(self.client_daemon.local_dir_state[LAST_TIMESTAMP], ts2)

    @httpretty.activate
    def test_on_moved(self):
        """
        Test that daemon on_moved method cause the user path being correctly moved inside client_snapshot attribute,
        global md5 changed, last timestamp correctly updated and local dir state saved.
        """
        # Create arbitrary initial values.
        ts0 = 1403878699
        ts1 = ts0 + 1
        src_path = 'dir1/tomove.txt'
        dest_path = 'dir2/tomove.txt'
        content = 'arbitrary content'
        md5 = hashlib.md5(content).hexdigest()
        global_md5 = 'fake global md5'  # the real value doesn't really matter in this test.

        # Create daemon initial state.
        self.client_daemon.client_snapshot = {src_path: [ts0, md5]}  # the path that will be moved.
        self.client_dir_state = {LAST_TIMESTAMP: ts0, GLOBAL_MD5: global_md5}

        # Create fake event and file.
        src_abs_path = os.path.join(self.sharing_path, src_path)
        dest_abs_path = os.path.join(self.sharing_path, dest_path)
        event = FileFakeEvent(src_abs_path, content, dest_abs_path)

        # Create server response.
        url = self.actions_url + 'move'  # NB: no final '/'!!!
        httpretty.register_uri(httpretty.POST, url,
                               status=200,
                               body='{"server_timestamp":%d}' % ts1,
                               content_type="application/json")

        # Store some initial values.
        local_dir_state_ts_start = os.path.getmtime(self.local_dir_state_path)
        glob_md5_start = self.client_daemon.local_dir_state[GLOBAL_MD5]

        # Call method to test.
        self.client_daemon.on_moved(event)

        # Store some final values to be compared.
        glob_md5_end = self.client_daemon.local_dir_state[GLOBAL_MD5]
        last_timestamp = self.client_daemon.local_dir_state[LAST_TIMESTAMP]

        # Test assertions.
        self.assertIn(dest_path, self.client_daemon.client_snapshot)
        self.assertNotIn(src_path, self.client_daemon.client_snapshot)
        self.assertNotEqual(glob_md5_start, glob_md5_end)  # md5 must be changed.
        # Last timestamp must be correctly updated with which one received from server.
        self.assertEqual(last_timestamp, ts1)
        # Check that state is saved on disk by checking if current file timestamp
        # is greater than the starting one.
        self.assertLess(local_dir_state_ts_start, os.path.getmtime(self.local_dir_state_path))


if __name__ == '__main__':
    unittest.main()

