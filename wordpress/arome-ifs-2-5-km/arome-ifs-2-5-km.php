<?php
/**
 * Plugin Name: AROME-IFS Météo-France France — Prévisions communales
 * Plugin URI: https://github.com/alertesmeteo-hub/AROME-IFS-2.5-km
 * Description: Prévisions communales horaires AROME-IFS de Météo-France pour la France métropolitaine et la Corse.
 * Version: 1.0.1
 * Author: Alertes Météo Hub
 * Requires at least: 5.8
 * Requires PHP: 7.4
 * License: GPL-2.0-or-later
 */

if (!defined('ABSPATH')) {
    exit;
}

/*
 * Une ancienne copie du module peut parfois rester active sous un autre nom
 * de dossier. Dans ce cas, ne redéclarons pas ses fonctions : WordPress peut
 * ainsi charger la nouvelle archive sans erreur fatale "Cannot redeclare".
 */
if (function_exists('aifs_render_shortcode')) {
    return;
}

define('AIFS_VERSION', '1.0.1');
define('AIFS_RELEASE_DATE', '09/09/2026');
define('AIFS_OPTION_BASE_URL', 'aifs_national_data_base_url');
define(
    'AIFS_DEFAULT_BASE_URL',
    'https://raw.githubusercontent.com/alertesmeteo-hub/AROME-IFS-2.5-km/data'
);

add_action('wp_enqueue_scripts', 'aifs_register_assets');
add_action('admin_init', 'aifs_register_settings');
add_action('admin_menu', 'aifs_add_settings_page');
add_shortcode('arome_ifs_meteo', 'aifs_render_shortcode');
add_filter('plugin_action_links_' . plugin_basename(__FILE__), 'aifs_plugin_action_links');

function aifs_plugin_action_links($links) {
    $settings_link = sprintf(
        '<a href="%s">%s</a>',
        esc_url(admin_url('options-general.php?page=arome-ifs-2-5-km')),
        esc_html__('Réglages', 'arome-ifs-2-5-km')
    );
    array_unshift($links, $settings_link);

    $help_link = sprintf(
        '<a href="%s">%s</a>',
        esc_url(admin_url('options-general.php?page=arome-ifs-2-5-km')),
        esc_html__('Shortcodes / Aide', 'arome-ifs-2-5-km')
    );
    array_unshift($links, $help_link);

    return $links;
}

function aifs_register_assets() {
    wp_register_style(
        'aifs-table',
        plugin_dir_url(__FILE__) . 'assets/arome-meteo.css',
        array(),
        AIFS_VERSION
    );
    wp_register_script(
        'aifs-table',
        plugin_dir_url(__FILE__) . 'assets/arome-meteo.js',
        array(),
        AIFS_VERSION,
        true
    );

}

function aifs_register_settings() {
    register_setting(
        'aifs_settings',
        AIFS_OPTION_BASE_URL,
        array(
            'type' => 'string',
            'sanitize_callback' => 'esc_url_raw',
            'default' => AIFS_DEFAULT_BASE_URL,
        )
    );

    add_settings_section(
        'aifs_main_section',
        'Source des données nationales',
        '__return_false',
        'arome-ifs-2-5-km'
    );

    add_settings_field(
        'aifs_data_base_url_field',
        'Adresse du dossier de données',
        'aifs_render_url_field',
        'arome-ifs-2-5-km',
        'aifs_main_section'
    );
}

function aifs_render_url_field() {
    $value = get_option(AIFS_OPTION_BASE_URL, AIFS_DEFAULT_BASE_URL);
    printf(
        '<input type="url" class="regular-text code" name="%1$s" value="%2$s" autocomplete="off">',
        esc_attr(AIFS_OPTION_BASE_URL),
        esc_attr($value)
    );
    echo '<p class="description">Conservez l’adresse proposée : elle pointe vers la branche nationale « data » du dépôt.</p>';
}

function aifs_add_settings_page() {
    add_options_page(
        'Tableau AROME-IFS Météo-France France',
        'AROME-IFS Météo-France',
        'manage_options',
        'arome-ifs-2-5-km',
        'aifs_render_settings_page'
    );
}

function aifs_render_settings_page() {
    if (!current_user_can('manage_options')) {
        return;
    }
    ?>
    <div class="wrap">
        <h1>AROME-IFS Météo-France France</h1>
        <form action="options.php" method="post">
            <?php
            settings_fields('aifs_settings');
            do_settings_sections('arome-ifs-2-5-km');
            submit_button();
            ?>
        </form>
        <p><strong>Version du module : <?php echo esc_html(AIFS_VERSION); ?> (<?php echo esc_html(AIFS_RELEASE_DATE); ?>)</strong></p>
        <h2>Shortcode unique</h2>
        <p><code>[arome_ifs_meteo]</code> : prévisions générales, orages, neige et graphiques.</p>
        <p><code>[arome_ifs_meteo code="75056" departement="75" ville="Paris" heures="51"]</code></p>
        <p><code>[arome_ifs_meteo code="66136" departement="66" ville="Perpignan" selecteur="non"]</code> : une seule ville, sans recherche.</p>
        <p>Le visiteur peut ensuite rechercher n’importe quelle commune ou saisir un code postal.</p>
    </div>
    <?php
}

function aifs_base_url() {
    $url = get_option(AIFS_OPTION_BASE_URL, AIFS_DEFAULT_BASE_URL);
    return untrailingslashit(apply_filters('aifs_national_data_base_url', $url));
}

function aifs_department_code($value) {
    $code = strtoupper(trim((string) $value));
    return preg_match('/^(?:\d{2}|2A|2B)$/', $code) ? $code : '66';
}

function aifs_commune_code($value) {
    $code = strtoupper(trim((string) $value));
    return preg_match('/^[0-9A-Z]{5}$/', $code) ? $code : '66136';
}

function aifs_unique_identifier() {
    if (function_exists('wp_unique_id')) {
        return wp_unique_id('aifs-city-');
    }
    return 'aifs-city-' . wp_rand(1000, 999999);
}

function aifs_render_shortcode($atts) {
    $atts = shortcode_atts(
        array(
            'ville' => 'Perpignan',
            'code' => '66136',
            'departement' => '66',
            'heures' => '51',
            'titre' => '',
            'selecteur' => 'oui',
        ),
        $atts,
        'arome_ifs_meteo'
    );

    $hours = max(1, min(51, absint($atts['heures'])));
    $city_name = sanitize_text_field($atts['ville']);
    if ($city_name === '') {
        $city_name = 'Perpignan';
    }
    $city_code = aifs_commune_code($atts['code']);
    $department = aifs_department_code($atts['departement']);
    $title_prefix = trim(sanitize_text_field($atts['titre']));
    if ($title_prefix === '') {
        $title_prefix = 'Prévisions AROME-IFS';
    }
    $selector_value = strtolower(trim(sanitize_text_field($atts['selecteur'])));
    $show_selector = !in_array($selector_value, array('non', '0', 'false', 'off'), true);

    $input_id = aifs_unique_identifier();
    $results_id = $input_id . '-results';
    $status_id = $input_id . '-status';

    wp_enqueue_style('aifs-table');
    wp_enqueue_script('aifs-table');

    ob_start();
    ?>
    <section
        class="aifs-card aifs-national"
        data-aifs-app
        data-base-url="<?php echo esc_url(aifs_base_url()); ?>"
        data-default-code="<?php echo esc_attr($city_code); ?>"
        data-default-department="<?php echo esc_attr($department); ?>"
        data-default-name="<?php echo esc_attr($city_name); ?>"
        data-hours="<?php echo esc_attr($hours); ?>"
        data-timezone="<?php echo esc_attr(wp_timezone_string()); ?>"
        data-title-prefix="<?php echo esc_attr($title_prefix); ?>"
        data-selector="<?php echo $show_selector ? '1' : '0'; ?>"
    >
        <header class="aifs-header">
            <div>
                <p class="aifs-kicker">MODÈLE HAUTE RÉSOLUTION • FRANCE MÉTROPOLITAINE</p>
                <h2 data-aifs-title><?php echo esc_html($title_prefix . ' — ' . $city_name); ?></h2>
                <p class="aifs-city-altitude" data-aifs-altitude>Altitude de <?php echo esc_html($city_name); ?> : chargement…</p>
                <p class="aifs-meta" data-aifs-meta>Chargement du dernier run AROME-IFS…</p>
            </div>
            <div class="aifs-badge">AROME-IFS<br><strong>2,5 km</strong></div>
        </header>

        <div class="aifs-toolbar" <?php if (!$show_selector) : ?>hidden<?php endif; ?>>
            <div class="aifs-search">
                <label for="<?php echo esc_attr($input_id); ?>">Choisissez votre commune</label>
                <div class="aifs-search-control">
                    <span class="aifs-search-icon" aria-hidden="true">⌕</span>
                    <input
                        id="<?php echo esc_attr($input_id); ?>"
                        class="aifs-city-input"
                        type="search"
                        value="<?php echo esc_attr($city_name); ?>"
                        placeholder="Nom de commune ou code postal"
                        autocomplete="off"
                        spellcheck="false"
                        role="combobox"
                        aria-autocomplete="list"
                        aria-expanded="false"
                        aria-controls="<?php echo esc_attr($results_id); ?>"
                        aria-describedby="<?php echo esc_attr($status_id); ?>"
                    >
                </div>
                <button type="button" class="aifs-locate-button" data-aifs-locate>📍 Détecter ma ville</button>
                <div
                    id="<?php echo esc_attr($results_id); ?>"
                    class="aifs-search-results"
                    role="listbox"
                    hidden
                ></div>
                <p
                    id="<?php echo esc_attr($status_id); ?>"
                    class="aifs-search-status"
                    role="status"
                    aria-live="polite"
                >Saisissez au moins deux lettres ou un code postal.</p>
            </div>
            <div class="aifs-coverage">
                <strong>34 746 communes</strong>
                <span>Métropole et Corse</span>
            </div>
        </div>

        <p class="aifs-stale" data-aifs-stale role="status" hidden>
            Attention : la dernière mise à jour disponible a plus de 8 heures.
        </p>

        <div class="aifs-tabs" role="tablist" aria-label="Type de prévision AROME-IFS">
            <button
                type="button"
                class="aifs-tab is-active"
                role="tab"
                aria-selected="true"
                data-aifs-tab="general"
            >🌤️ Prévisions générales</button>
            <button
                type="button"
                class="aifs-tab aifs-tab-storm"
                role="tab"
                aria-selected="false"
                data-aifs-tab="storms"
            >⛈️ Prévisions orages</button>
            <button
                type="button"
                class="aifs-tab aifs-tab-snow"
                role="tab"
                aria-selected="false"
                data-aifs-tab="snow"
            >❄️ Risque de neige</button>
        </div>

        <div class="aifs-panel" data-aifs-panel="general">
            <div class="aifs-table-wrap aifs-general-wrap" role="region" aria-label="Prévisions horaires générales" tabindex="0">
                <table class="aifs-table">
                    <thead>
                        <tr>
                            <th scope="col">Date</th>
                            <th scope="col">Heure</th>
                            <th scope="col">Temps</th>
                            <th scope="col">T°</th>
                            <th scope="col">Hum.</th>
                            <th scope="col">Pluie</th>
                            <th scope="col">Nuages</th>
                            <th scope="col">Vent</th>
                            <th scope="col">Rafales</th>
                            <th scope="col">Pression</th>
                        </tr>
                    </thead>
                    <tbody data-aifs-body-general>
                        <tr>
                            <td colspan="10" class="aifs-loading">Chargement des prévisions…</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <section class="aifs-charts" data-aifs-charts aria-label="Diagrammes AROME-IFS">
                <article class="aifs-chart-card">
                    <h3 data-aifs-chart-title-temperature>Diagramme températures (°C)</h3>
                    <div class="aifs-chart" data-aifs-chart-temperature></div>
                </article>
                <article class="aifs-chart-card">
                    <h3 data-aifs-chart-title-pressure>Diagramme pression ramenée au niveau de la mer (hPa)</h3>
                    <div class="aifs-chart" data-aifs-chart-pressure></div>
                </article>
                <article class="aifs-chart-card">
                    <h3 data-aifs-chart-title-rain>Diagramme précipitations (mm)</h3>
                    <p class="aifs-chart-total" data-aifs-rain-total>Précipitations cumulées : —</p>
                    <div class="aifs-chart" data-aifs-chart-rain></div>
                </article>
                <article class="aifs-chart-card">
                    <h3 data-aifs-chart-title-wind>Diagramme rafales et vent moyen</h3>
                    <div class="aifs-chart" data-aifs-chart-wind></div>
                </article>
            </section>
        </div>

        <div class="aifs-panel" data-aifs-panel="storms" hidden>
            <p class="aifs-storm-summary" data-aifs-storm-summary>
                Diagnostic convectif AROME-IFS 0,025° : chargement…
            </p>
            <div class="aifs-top-scroll" data-aifs-top-scroll="storms" aria-label="Navigation horizontale du tableau orages" hidden><div></div></div>
            <div class="aifs-table-wrap aifs-storm-wrap" data-aifs-scroll-wrap="storms" role="region" aria-label="Prévisions horaires d'orages" tabindex="0">
                <table class="aifs-table aifs-storm-table">
                    <thead>
                        <tr>
                            <th scope="col">Date</th>
                            <th scope="col">Heure</th>
                            <th scope="col">Risque orage</th>
                            <th scope="col">CAPE</th>
                            <th scope="col">LCL estimé</th>
                            <th scope="col">Foudre</th>
                            <th scope="col">Grêle</th>
                            <th scope="col">Pluie conv.</th>
                            <th scope="col">Graupel</th>
                            <th scope="col">Pluie 1 h</th>
                            <th scope="col">Rafales</th>
                            <th scope="col">Type</th>
                            <th scope="col">Détails</th>
                        </tr>
                    </thead>
                    <tbody data-aifs-body-storms>
                        <tr>
                            <td colspan="13" class="aifs-loading">Chargement du diagnostic orageux…</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <p class="aifs-storm-note">
                <strong>Lecture expert :</strong> la CAPE est une sortie directe AROME-IFS. Le risque orage est indicatif et dérivé de la CAPE et des rafales. La réflectivité, la foudre, la grêle et le type d’orage sont indisponibles et affichés par un tiret.
            </p>
        </div>

        <div class="aifs-panel" data-aifs-panel="snow" hidden>
            <p class="aifs-snow-summary" data-aifs-snow-summary>
                Diagnostic neige AROME-IFS 0,025° : chargement…
            </p>
            <div class="aifs-top-scroll" data-aifs-top-scroll="snow" aria-label="Navigation horizontale du tableau neige" hidden><div></div></div>
            <div class="aifs-table-wrap aifs-snow-wrap" data-aifs-scroll-wrap="snow" role="region" aria-label="Risque horaire de neige" tabindex="0">
                <table class="aifs-table aifs-snow-table">
                    <thead>
                        <tr>
                            <th scope="col">Date</th>
                            <th scope="col">Heure</th>
                            <th scope="col">Risque neige</th>
                            <th scope="col">Phase</th>
                            <th scope="col">Neige 1 h</th>
                            <th scope="col">Neige 3 h</th>
                            <th scope="col">Neige 6 h</th>
                            <th scope="col">Tenue</th>
                            <th scope="col">Pres. hPa</th>
                            <th scope="col">Hum.</th>
                            <th scope="col">Vent moy. / raf.</th>
                            <th scope="col">Cumul neige fraîche</th>
                            <th scope="col">Détails</th>
                        </tr>
                    </thead>
                    <tbody data-aifs-body-snow>
                        <tr>
                            <td colspan="13" class="aifs-loading">Chargement du risque de neige…</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            <p class="aifs-snow-note">
                <strong>Lecture neige :</strong> les cumuls de neige sont des sorties directes AROME-IFS. La neige fraîche et la tenue sont estimées à partir du cumul en eau, de la température à 2 m et de l’altitude du point de grille.
            </p>
        </div>

        <footer class="aifs-footer">
            <span data-aifs-generated>Mise à jour en cours de lecture…</span>
            <span>
                Données météo directes :
                <a href="https://www.data.gouv.fr/datasets/paquets-arome-resolution-0-01deg" target="_blank" rel="noopener noreferrer">AROME-IFS 0,025° — Météo-France</a>
                • Recherche des communes :
                <a href="https://geo.api.gouv.fr/decoupage-administratif/communes" target="_blank" rel="noopener noreferrer">API officielle française</a>
                • <a href="https://www.alertes-meteo.com/" target="_blank" rel="noopener noreferrer">www.alertes-meteo.com</a>
            </span>
            <span class="aifs-plugin-version">Module AROME-IFS v<?php echo esc_html(AIFS_VERSION); ?> (<?php echo esc_html(AIFS_RELEASE_DATE); ?>)</span>
        </footer>

        <noscript>
            <p class="aifs-message aifs-error">JavaScript doit être activé pour rechercher une commune.</p>
        </noscript>
    </section>
    <?php
    return ob_get_clean();
}
