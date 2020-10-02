var path = require("path");
var webpack = require("webpack");

module.exports = function(env) {

	var pack = require("./package.json");
	var MiniCssExtractPlugin = require("mini-css-extract-plugin");

	var production = !!(env && env.production === "true");
	var asmodule = !!(env && env.module === "true");

	var babelSettings = {
		extends: path.join(__dirname, '/.babelrc')
	};

	var config = {
		mode: production ? "production" : "development",
		entry: {
			app: "./sources/app.js"
		},
		output: {
			path: path.join(__dirname, "codebase"),
			publicPath:"/codebase/",
			filename: "[name].js",
			library: "csvexceldownload",
			libraryTarget : "umd"
		},
		module: {
			rules: [
				{
					test: /\.js$/,
					exclude(modulePath) {
						return /node_modules/.test(modulePath) &&
							!/node_modules[\\/]webix-jet/.test(modulePath) &&
							!/node_modules[\\/]webpack-dev-server/.test(modulePath);
					},
					use: "babel-loader?" + JSON.stringify(babelSettings)
				},
				{
					test: /\.(svg|png|jpg|gif)$/,
					use: "url-loader?limit=25000"
				},
				{
					test: /\.(less|css)$/,
					use: [
						MiniCssExtractPlugin.loader,
						"css-loader",
						"less-loader"
					]
				}
			]
		},
		resolve: {
			extensions: [".js"],
			modules: ["./sources", "node_modules", "./codebase"],
			alias:{
				"jet-views":path.resolve(__dirname, "sources/views")
			}
		},
		plugins: [
			new MiniCssExtractPlugin({
				filename:"[name].css"
			}),
			new webpack.DefinePlugin({
				VERSION: `"${pack.version}"`,
				APPNAME: `"${pack.name}"`,
				PRODUCTION : production
			}),
			new webpack.IgnorePlugin(/jet-locales/) // to ignore jet-locales
		],
		devServer:{
			stats:"errors-only"
		}
	};

	if (!production){
		config.devtool = "inline-source-map";
	}

	if (asmodule){
		config.externals = config.externals || {};
		config.externals = [ "webix-jet" ];
	}

	return config;
};