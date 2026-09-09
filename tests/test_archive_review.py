import json
from pathlib import Path
import tempfile
import unittest

from regression.archive_review import archive
from regression.common import sha256


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root/'runs'/'example'
        self.run.mkdir(parents=True)
        self.reviews = self.root/'reviews'
        source = self.run/'sources'/'region_mask'/'oceans.py'
        source.parent.mkdir(parents=True)
        source.write_text('# exact generating source\n')
        (self.run/'manifest.json').write_text(json.dumps({
            'reference_commit':'abc123', 'inputs':{'input.shp':'hash'},
            'sources':{'region_mask/oceans.py':sha256(source)}}))
        (self.run/'stages.json').write_text('{}')
        (self.run/'total.json').write_text('{}')
        (self.run/'atlas.json').write_text('[{"figure":"figures/00.png"}]')
        (self.run/'figures').mkdir()
        (self.run/'figures/00.png').write_bytes(b'fixture image')
        (self.run/'report.md').write_text('# Review\n\n![Map](figures/00.png)\n[Web](https://example.org)\n')

    def test_archive_preserves_sources_excludes_data_and_hashes_payload(self):
        (self.run/'large.gpkg').write_bytes(b'not evidence')
        result=archive(self.run,self.reviews,'review-one')
        self.assertFalse((result/'large.gpkg').exists())
        self.assertEqual((result/'sources/region_mask/oceans.py').read_bytes(),
                         (self.run/'sources/region_mask/oceans.py').read_bytes())
        metadata=json.loads((result/'archive.json').read_text())
        for name,digest in metadata['archived_sha256'].items():
            self.assertEqual(sha256(result/name),digest)
        self.assertEqual(metadata['status'],'awaiting_review')

    def test_existing_archive_is_never_overwritten(self):
        result=archive(self.run,self.reviews,'review-one')
        before=(result/'archive.json').read_bytes()
        with self.assertRaises(FileExistsError):archive(self.run,self.reviews,'review-one')
        self.assertEqual((result/'archive.json').read_bytes(),before)

    def test_broken_link_fails_before_creating_archive(self):
        (self.run/'report.md').write_text('[Missing](absent.png)')
        with self.assertRaises(ValueError):archive(self.run,self.reviews,'review-one')
        self.assertFalse((self.reviews/'review-one').exists())

    def test_source_checksum_mismatch_fails(self):
        (self.run/'sources/region_mask/oceans.py').write_text('modified')
        with self.assertRaisesRegex(ValueError,'checksum'):archive(self.run,self.reviews,'review-one')
        self.assertFalse((self.reviews/'review-one').exists())

    def test_sibling_report_links_are_bundled_and_rewritten(self):
        sibling=self.run.parent/'support';sibling.mkdir()
        (sibling/'report.md').write_text('[Metrics](metrics.json)\n[Back](../example/report.md)')
        (sibling/'metrics.json').write_text('{}')
        (self.run/'reviewer_notes.md').write_text('[Support](../support/report.md)')
        result=archive(self.run,self.reviews,'review-one')
        self.assertIn('(related/support/report.md)',(result/'reviewer_notes.md').read_text())
        self.assertIn('(../../report.md)',(result/'related/support/report.md').read_text())
        self.assertTrue((result/'related/support/metrics.json').exists())

    def test_path_escape_and_invalid_name_are_rejected(self):
        with self.assertRaises(ValueError):archive(self.run,self.reviews,'../escape')
        (self.root/'secret.json').write_text('{}')
        (self.run/'report.md').write_text('[Secret](../../secret.json)')
        with self.assertRaises(ValueError):archive(self.run,self.reviews,'review-one')

    def test_link_to_dataset_is_rejected(self):
        (self.run/'large.gpkg').write_bytes(b'dataset')
        (self.run/'report.md').write_text('[Data](large.gpkg)')
        with self.assertRaises(ValueError):archive(self.run,self.reviews,'review-one')
