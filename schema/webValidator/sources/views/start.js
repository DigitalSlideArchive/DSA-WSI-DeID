import {JetView} from "webix-jet";
import Ajv from "ajv";
import UploadMetadataService from "../services/rootService";
// import validationSchema from "../schemas/sample_schema.json";
import {errorsCollection} from "../models/errors";

const ajv = new Ajv({allErrors: true});
// ajv.addSchema(validationSchema, "data");

export default class UploadMetadataView extends JetView {
	config() {
		const uploader = {
			view: "uploader",
			autosend: false,
			value: "Upload file",
			multiple: true
		};

		const filesDropDown = {
			view: "richselect",
			tooltip: () => this.filesDropDown.getText(),
			name: "filesDropDown",
			css: "files-dropdown select-field ellipsis-text",
			label: "Files",
			labelWidth: 70,
			disabled: true,
			width: 300,
			options: {
				body: {
					css: "files-list",
					template: obj => `<div class='ellipsis-text files-list-item'><span class='list-item-text' title='${obj.name}'>${obj.name}</span><i class='list-item-icon delete-icon fas fa-times'></i></div>`,
					data: []
				}
			}
		};

		const uploaderLayout = {
			name: "uploaderLayout",
			padding: 10,
			width: 500,
			height: 100,
			cols: [
				{
					rows: [
						filesDropDown
					]
				},
				{width: 40},
				{
					rows: [
						uploader,
						{}
					]
				}
			]
		};

		const datatable = {
			view: "datatable",
			name: "metaDatatable",
			select: "row",
			navigation: false,
			editable: true,
			editaction: "custom",
			css: "upload-metadatatable",
			resizeColumn: true,
			tooltip: true,
			borderless: true,
			data: [],
			rules: {
				$obj: (obj) => {
					// the spot for using AJV schema validators
					const schema = webix.storage.local.get("currentSchema");
					if (schema) {
						const validate = ajv.compile(JSON.parse(schema));
						const valid = validate(obj);
						if (!valid) {
							errorsCollection[obj.id] = validate.errors;
							validate.errors.forEach((err) => {
								const dataPath = err.dataPath;
								if (dataPath) {
									const columnName = dataPath.slice(1);
									this.metaDatatable.addCellCss(obj.id, columnName, "invalid-cell");
								}
							});
							this.metaDatatable.refresh(obj.id);
						}
					}
					return true;
				}
			}
		};

		const mainView = {
			name: "uploadMetadataView",
			paddingX: 10,
			rows: [
				{
					cols: [
						{
							padding: 10,
							rows: [
								{
									view: "form",
									type: "clean",
									borderless: true,
									rules: {
										url: webix.rules.isNotEmpty
									},
									elements: [
										{
											cols: [
												{
													view: "text",
													name: "url",
													placeholder: "Enter the Schema URL",
													label: "Schema URL",
													invalidMessage: "Please, enter the schema URL",
													width: 300,
													labelWidth: 100
												},
												{width: 20},
												{
													view: "button",
													name: "loadSchemaButton",
													value: "Load schema",
													css: "webix_primary ",
													width: 120
												}
											]
										}
									]
								},
								{}	
							]
						},
						{},
						{
							padding: 10,
							rows: [
								{
									borderless: true,
									name: "schemaStatusTemplate",
									css: "schema-status",
									template: ({progress}) => {
										const schema = webix.storage.local.get("currentSchema");
										let status = schema ? "<i style='color: green' class='fas fa-thumbs-up'></i> Schema cached" : "<i style='color: red' class='fas fa-thumbs-down'></i> Schema doesn't exist";
										if (progress) status = "<i style='color: orange' class='fas fa-spinner fa-spin'></i> In progress";
										return `<div>${status}</div>`;
									}
								},
								{}
							]
						},
						{},
						uploaderLayout
					]
				},
				{
					gravity: 5,
					rows: [
						datatable
					]
				}
			]
		};

		return mainView;
	}

	ready(view) {
		this._service = new UploadMetadataService(view);
	}

	get uploader() {
		return this.getRoot().queryView({view: "uploader"});
	}

	get uploaderLayout() {
		return this.getRoot().queryView({name: "uploaderLayout"});
	}

	get uploadMetadataView() {
		return this.getRoot();
	}

	get filesDropDown() {
		return this.getRoot().queryView({name: "filesDropDown"});
	}

	get metaDatatable() {
		return this.getRoot().queryView({name: "metaDatatable"});
	}

	get loadSchemaButton() {
		return this.getRoot().queryView({name: "loadSchemaButton"});
	}

	get schemaStatusTemplate() {
		return this.getRoot().queryView({name: "schemaStatusTemplate"});
	}
}
