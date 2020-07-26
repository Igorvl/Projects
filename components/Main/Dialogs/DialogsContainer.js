// import React from 'react';
import {addNewComment, addNewCommentText} from "../../Redux/dialogsReducer";
import Dialogs from "./Dialogs";
import {connect} from "react-redux";
import withAuthRedirect from "../../HOC/withAuthRedirect";

const mapStateToProps = (state) => {
	return ({
		// data from (redux-store)-state for Dialogs. Default values defined in redux-store and dialogReducer
		dialogData: state.dialogsPage.dialogData,
		messageData: state.dialogsPage.messageData,
		newCommentTxt: state.dialogsPage.newCommentTxt,
	})
};

let AuthRedirectComponent = withAuthRedirect(Dialogs);

export default connect(mapStateToProps, {addNewCommentText,addNewComment})(AuthRedirectComponent);

