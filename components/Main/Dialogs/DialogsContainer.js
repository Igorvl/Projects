// import React from 'react';
import {addNewComment, addNewCommentText} from "../../Redux/dialogsReducer";
import Dialogs from "./Dialogs";
import {connect} from "react-redux";
import withAuthRedirect from "../../HOC/withAuthRedirect";
import {compose} from "redux";

const mapStateToProps = (state) => {
	return ({
		// data from (redux-store)-state for Dialogs. Default values defined in redux-store and dialogReducer
		dialogData: state.dialogsPage.dialogData,
		messageData: state.dialogsPage.messageData,
		newCommentTxt: state.dialogsPage.newCommentTxt,
	})
};

// все ф-и последовательной обработки Dialogs переносим в конвеер compose (ф-я Redux). Порядок выполнения:
// withAuthRedirect, connect

export default compose(
	connect(mapStateToProps, {addNewCommentText,addNewComment}),
	withAuthRedirect,
)(Dialogs);



