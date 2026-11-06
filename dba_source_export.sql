/*
ORA-00979 reviewer - DBA_SOURCE CSV export

1. Replace APP1 and APP2 below with dictionary OWNER names.
2. Run the SELECT in your SQL client.
3. Export ALL result rows to dba_source.csv, not only the visible page.

Required export settings:
  Format: CSV (not XLSX, HTML or formatted plain text)
  Encoding: UTF-8
  Header: enabled, exact columns OWNER,NAME,TYPE,LINE,TEXT
  Separator: comma (,)
  String delimiter: double quote (")
  Embedded double quotes: escaped by doubling (CSV standard)
  Preserve TEXT exactly, including embedded newlines and whitespace.
  Disable trimming, value truncation and row limits.
  Do not open/save the source CSV through Excel before importing.

Do NOT filter individual source lines using TEXT LIKE '%GROUP BY%'.
The reviewer requires every line of each selected object.
For one object, optionally add AND name = 'OBJECT_NAME'.
Keep PACKAGE and PACKAGE BODY when collecting a package.

After copying the CSV to the project directory on RHEL:
  python review.py import dba_source.csv
  python review.py plan
  python review.py run --limit 5
  python review.py report --out reports/pilot

The import command replaces the active review scope with this entire snapshot.
Include all desired owners/objects in one CSV.
This SELECT only reads source metadata; it does not run the stored code.
*/
SELECT owner AS "OWNER",
       name  AS "NAME",
       type  AS "TYPE",
       line  AS "LINE",
       text  AS "TEXT"
FROM sys.dba_source
WHERE owner IN ('APP1', 'APP2')
  AND type IN (
      'PACKAGE', 'PACKAGE BODY',
      'PROCEDURE', 'FUNCTION', 'TRIGGER',
      'TYPE', 'TYPE BODY'
  )
ORDER BY owner, name, type, line;
