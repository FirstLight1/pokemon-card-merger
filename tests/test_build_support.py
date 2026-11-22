import unittest

from build_support import deduplicate_dlls


class BinaryCleanupTests(unittest.TestCase):
    def test_removes_only_root_copy_of_identical_packaged_dll(self):
        packaged = (r"torch\lib\torch_cpu.dll", r"C:\env\torch\lib\torch_cpu.dll", "BINARY")
        root = ("torch_cpu.dll", packaged[1], "BINARY")
        self.assertEqual(deduplicate_dlls([packaged, root]), [packaged])

    def test_preserves_different_sources_and_unique_root_libraries(self):
        entries = [
            (r"package\runtime.dll", r"C:\one\runtime.dll", "BINARY"),
            ("runtime.dll", r"C:\two\runtime.dll", "BINARY"),
            ("python312.dll", r"C:\Python312\python312.dll", "BINARY"),
        ]
        self.assertEqual(deduplicate_dlls(entries), entries)

    def test_preserves_extension_modules_and_data(self):
        entries = [
            (r"package\module.pyd", r"C:\env\module.pyd", "BINARY"),
            ("module.pyd", r"C:\env\module.pyd", "BINARY"),
            (r"package\data.dll", r"C:\env\data.dll", "DATA"),
            ("data.dll", r"C:\env\data.dll", "DATA"),
        ]
        self.assertEqual(deduplicate_dlls(entries), entries)


if __name__ == "__main__":
    unittest.main()
