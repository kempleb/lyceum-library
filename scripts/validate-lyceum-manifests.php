<?php
// Runs Brian's Reader Manager validator (LRM_Manifest_Validator, vendored under
// docs/lyceum-build/handoff-2026-09-12/reference/plugin/includes/) over every
// emitted partner manifest in build/dist/*/manifest.lyceum.json.
//
// Usage, from the repo root:  php scripts/validate-lyceum-manifests.php [dist-dir]
// Exit 0 when every manifest passes both validate() and validate_batch(); 1 when any
// fails; 2 when no manifests are found under the dist directory.
// Prints one line per failing manifest and a tally of distinct error messages.

define( 'LRM_TESTING', true );
$root = dirname( __DIR__ );
require $root . '/docs/lyceum-build/handoff-2026-09-12/reference/plugin/includes/class-lrm-manifest-validator.php';

$dist  = $argv[1] ?? $root . '/build/dist';
$files = glob( $dist . '/*/manifest.lyceum.json' ) ?: array();
sort( $files );
if ( ! $files ) { fwrite( STDERR, "no manifests under $dist\n" ); exit( 2 ); }

$manifests = array(); $failed = 0; $tally = array();
foreach ( $files as $file ) {
	$m = json_decode( file_get_contents( $file ), true );
	if ( ! is_array( $m ) ) { echo "PARSE  $file\n"; $failed++; continue; }
	$manifests[] = $m;
	$errors = LRM_Manifest_Validator::validate( $m );
	if ( $errors ) {
		$failed++;
		echo 'FAIL   ' . basename( dirname( $file ) ) . ': ' . implode( ' | ', $errors ) . "\n";
		foreach ( $errors as $e ) $tally[ $e ] = ( $tally[ $e ] ?? 0 ) + 1;
	}
}
$batch = LRM_Manifest_Validator::validate_batch( $manifests );
foreach ( $batch as $e ) { echo "BATCH  $e\n"; $tally[ $e ] = ( $tally[ $e ] ?? 0 ) + 1; }

printf( "\n%d manifests, %d failed validate(), %d batch errors\n", count( $files ), $failed, count( $batch ) );
foreach ( $tally as $msg => $n ) printf( "%4d  %s\n", $n, $msg );
exit( ( $failed || $batch ) ? 1 : 0 );
