import json
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import update_arome_ifs as model


class ContractTests(unittest.TestCase):
    def test_exact_shared_columns(self):
        reference = json.loads((ROOT / 'tests/reference-schema.json').read_text())
        self.assertEqual(list(model.schema.VALUE_COLUMNS), reference['values'])
        self.assertEqual(len(reference['values']), 33)

    def test_hourly_accumulations_units_and_nulls(self):
        raw = {key: np.array([value]) for key, value in {
            'temperature_k': 273.15, 'humidity_pct': 90,
            'wind_u_ms': 3, 'wind_v_ms': 4, 'gust_speed_ms': 10,
            'surface_pressure_pa': 100000, 'sea_pressure_pa': 101300,
            'cape_jkg': 600, 'precipitation_total_mm': 5,
            'snow_total_mm': 2, 'graupel_total_mm': .2,
            'cloud_low_pct': 50, 'cloud_mid_pct': 0, 'cloud_high_pct': 0,
        }.items()}
        previous = {'rain_total': np.array([2.]), 'snow_total': np.array([1.]),
                    'graupel_total': np.array([.1])}
        data, _ = model.transform(raw, np.array([0.]), previous, 2)
        row = model.schema.compact_rows(data, np.array([0]))[0]
        values = dict(zip(model.schema.VALUE_COLUMNS, row))
        self.assertEqual(values['temperature_c'], 0)
        self.assertEqual(values['precipitation_mm'], 3)
        self.assertEqual(values['precipitation_total_mm'], 5)
        self.assertEqual(values['snowfall_mm'], 1)
        self.assertEqual(values['wind_speed_kmh'], 18)
        self.assertEqual(values['wind_gust_kmh'], 36)
        self.assertEqual(values['pressure_hpa'], 1013)
        self.assertEqual(values['thunder_risk_code'], 2)
        for field in ('reflectivity_dbz', 'visibility_km', 'lightning_score',
                      'hail_risk_code', 'convective_precipitation_mm', 'storm_type_code'):
            self.assertIsNone(values[field])
        json.dumps(row, allow_nan=False)

    def test_department_local_point_ids_and_writer(self):
        catalog = model.schema.load_catalog(ROOT / 'config/communes-france.json')
        self.assertEqual(len(catalog.departments), 96)
        self.assertGreater(catalog.commune_count, 34000)
        for department in catalog.departments.values():
            for commune in department.communes:
                point = department.points[commune[6]]
                self.assertEqual(point[0], model.schema.grid_index(commune[4], commune[5])[0])
        department = catalog.departments['66']
        for point in department.points:
            point.append(100)
        catalog.departments = {'66': department}
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            rows = [[None] * 33 for _ in department.points]
            (directory / '66.ndjson').write_text(json.dumps(['2026-09-07T18:00:00Z', rows]) + '\n')
            model.schema.write_departments(directory / 'out', directory, catalog, '2026-09-07T19:00:00Z')
            result = json.loads((directory / 'out/departements/66.json').read_text())
            reference = json.loads((ROOT / 'tests/reference-schema.json').read_text())
            self.assertEqual(result['schema_version'], reference['schema_version'])
            self.assertEqual(result['columns'], {k: reference[k] for k in ('points', 'communes', 'values')})
            self.assertEqual(result['forecast'][0][1], rows)

    def test_resource_selection_never_mixes_runs(self):
        resources = []
        for group in ('SP1', 'SP2'):
            for start, end in model.BLOCKS:
                title = f'aromeifs__0025__{group}__{start:02}H{end:02}H__2026-09-07T18:00:00Z.grib2'
                resources.append({'title': title, 'url': 'https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net/pnt/aromeifs/0025/' + title})
        resources.append({**resources[0], 'title': resources[0]['title'].replace('18:00', '21:00')})
        self.assertEqual(model.select_resources(resources)[0], '2026-09-07T18:00:00Z')
        with self.assertRaises(ValueError):
            model.select_resources(resources[1:])

    def test_step_units_and_truncated_packet(self):
        self.assertEqual(model.step_hours('180m'), 3)
        self.assertEqual(model.step_hours('6h'), 6)
        with self.assertRaises(ValueError):
            model.step_hours('90m')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.grib2'
            path.write_bytes(b'GRIB')
            with self.assertRaises(ValueError):
                list(model.messages(path))


if __name__ == '__main__':
    unittest.main()
