const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

// Evaluate the pure helpers without starting the dashboard or connecting to DB.
const source = fs.readFileSync(require.resolve('./index.js'), 'utf8');
const helpers = source.slice(source.indexOf('function parseHoursFromText('), source.indexOf('function normalizeRecord('));
const { parseHoursFromText, extractOperatingHours } = vm.runInNewContext(helpers + '\n({parseHoursFromText, extractOperatingHours})');

test('flattened year plus hours is not a million-hour reading', () => {
  assert.equal(parseHoursFromText('Year 2021 375 h'), null);
  assert.equal(parseHoursFromText('Year 2021, meter 1,375 hours'), 1375);
  assert.equal(parseHoursFromText('63,138 hrs'), 63138);
});

test('explicit source meter has priority and permits low hours', () => {
  assert.equal(extractOperatingHours({raw_json: {operating_hours: 25}, description: '2021 375 h'}), 25);
  assert.equal(extractOperatingHours({raw_json: '{"operating_hours":0}'}), 0);
  assert.equal(extractOperatingHours({raw_json: {operating_hours: null}, description: '3,080 hours'}), 3080);
  assert.equal(extractOperatingHours({raw_json: {operating_hours: 2021375}, description: '2021 375 h'}), null);
});
