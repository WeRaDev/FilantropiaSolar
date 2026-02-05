/**
 * Webpack Configuration for FilantropiaSolar Nextcloud App
 */

const path = require('path')
const { VueLoaderPlugin } = require('vue-loader')
const { DefinePlugin } = require('webpack')
const MiniCssExtractPlugin = require('mini-css-extract-plugin')

const isDev = process.env.NODE_ENV !== 'production'

module.exports = {
    mode: isDev ? 'development' : 'production',
    devtool: isDev ? 'source-map' : false,

    entry: {
        'filantropia_solar-main': path.resolve(__dirname, 'src/main.js'),
    },

    output: {
        path: path.resolve(__dirname, 'js'),
        filename: '[name].js',
        chunkFilename: '[name]-[contenthash].js',
        clean: true,
    },

    module: {
        rules: [
            {
                test: /\.vue$/,
                loader: 'vue-loader',
            },
            {
                test: /\.js$/,
                exclude: /node_modules/,
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: ['@babel/preset-env'],
                    },
                },
            },
            {
                test: /\.scss$/,
                use: [
                    isDev ? 'vue-style-loader' : MiniCssExtractPlugin.loader,
                    'css-loader',
                    {
                        loader: 'sass-loader',
                        options: {
                            additionalData: `@import "./src/style/_golden-brand.scss";`,
                        },
                    },
                ],
            },
            {
                test: /\.css$/,
                use: [
                    isDev ? 'vue-style-loader' : MiniCssExtractPlugin.loader,
                    'css-loader',
                ],
            },
            {
                test: /\.(png|jpe?g|gif|svg|woff2?|eot|ttf|otf)$/,
                type: 'asset/resource',
                generator: {
                    filename: 'assets/[name]-[hash][ext]',
                },
            },
        ],
    },

    plugins: [
        new VueLoaderPlugin(),
        new DefinePlugin({
            __VUE_OPTIONS_API__: true,
            __VUE_PROD_DEVTOOLS__: false,
            __VUE_PROD_HYDRATION_MISMATCH_DETAILS__: false,
        }),
        ...(isDev
            ? []
            : [
                new MiniCssExtractPlugin({
                    filename: '../css/[name].css',
                }),
            ]),
    ],

    resolve: {
        extensions: ['.js', '.vue', '.json'],
        alias: {
            vue: 'vue/dist/vue.esm-bundler.js',
            '@': path.resolve(__dirname, 'src'),
        },
    },

    optimization: {
        splitChunks: {
            chunks: 'async',
            cacheGroups: {
                vendor: {
                    test: /[\\/]node_modules[\\/]/,
                    name: 'vendor',
                    chunks: 'all',
                },
            },
        },
    },

    externals: {
        // Nextcloud provides these globally
    },

    stats: {
        errorDetails: true,
    },

    // Suppress size warnings - acceptable for this enterprise app
    performance: {
        hints: false,
        maxEntrypointSize: 1024000,  // 1MB
        maxAssetSize: 1024000,
    },
}
