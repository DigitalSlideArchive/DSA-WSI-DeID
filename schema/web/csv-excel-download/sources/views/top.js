import {JetView} from "webix-jet";

export default class TopView extends JetView{
	config(){

		const header = {
			view:"toolbar",
			css:"webix_dark", padding:{ left:8 },
			elements:[
				{ view:"label", label:this.app.config.name }
				/*wjet::Topbar*/
			]
		};

		// const menu = {
		// 	view:"sidebar", id:"top:menu", 
		// 	width:180, layout:"y", select:true,
		// 	template:"<span class='webix_icon #icon#'></span> #value# ",
		// 	data:[
		// 		{ value:"DashBoard", id:"start", icon:"wxi-plus-square" },
		// 		{ value:"Data",		 id:"data",  icon:"wxi-columns" },
		// 		{ value:"Settings",  id:"settings",  icon:"wxi-pencil" },
		// 		/*wjet::Menu*/
		// 	]
		// };

		const ui = {
			rows:[
				header,
				{ $subview:true }
			]
		};

		return ui;
	}

	init(){
		// this.use(plugins.Menu, "top:menu");
	}
}